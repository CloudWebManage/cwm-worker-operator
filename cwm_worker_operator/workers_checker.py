"""
Check workers and update status in Redis and local storage
"""
import json
import traceback
import subprocess

from cwm_worker_operator import config, common, logs
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import multiprocessor
from cwm_worker_operator.metrics import WorkersCheckerMetrics


def get_worker_ids(deployments_manager: DeploymentsManager, domains_config: DomainsConfig):
    worker_ids = set()
    for release in deployments_manager.iterate_all_releases():
        worker_ids.add(common.get_worker_id_from_namespace_name(release['namespace']))
    for worker_id in domains_config.keys.worker_health.iterate_prefix_key_suffixes():
        worker_ids.add(worker_id)
    for namespace_name in deployments_manager.get_all_namespaces():
        worker_id = common.get_worker_id_from_namespace_name(namespace_name)
        if worker_id != namespace_name:
            worker_ids.add(worker_id)
    return worker_ids


def process_worker(worker_id,
                   domains_config: DomainsConfig = None,
                   deployments_manager: DeploymentsManager = None,
                   now=None):
    if not domains_config:
        domains_config = DomainsConfig()
    if not deployments_manager:
        deployments_manager = DeploymentsManager()
    if now is None:
        now = common.now()
    if domains_config.is_valid_worker_id(worker_id):
        namespace_name = common.get_namespace_name_from_worker_id(worker_id)
        try:
            health = deployments_manager.get_health(namespace_name, 'minio')
        except:
            exception = traceback.format_exc()
            print("Failed to get health for worker_id {}".format(worker_id))
            print(exception)
            health = {
                'exception': exception
            }
        if health:
            domains_config.keys.worker_health.set(worker_id, json.dumps(health))
            common.local_storage_json_last_items_append(
                'workers_checker/health/{}'.format(worker_id),
                health, max_items=100,
                now_=now
            )
            worker_conditions = get_worker_conditions(worker_id)
        elif domains_config.keys.worker_health.exists(worker_id):
            domains_config.keys.worker_health.delete(worker_id)
            common.local_storage_json_last_items_append(
                'workers_checker/health/{}'.format(worker_id),
                {'__deleted': True}, max_items=100,
                now_=now
            )
            worker_conditions = get_worker_conditions(worker_id)
        else:
            worker_conditions = None
        if worker_conditions:
            common.local_storage_json_last_items_append(
                'workers_checker/conditions/{}'.format(worker_id),
                worker_conditions, max_items=100,
                now_=now
            )
        return worker_conditions
    else:
        return None


def process_worker_cli(*args, **kwargs):
    multiprocessor.print_json_response(process_worker(*args, **kwargs))
    return True


class HealthItemPodConditions:

    def __init__(self, pod):
        self.pod = pod
        self.phase_running = pod.get('phase') == 'Running'
        self.phase_pending = pod.get('phase') == 'Pending'
        self.condition_containers_ready = pod.get('conditions', {}).get('ContainersReady', '').startswith('True')
        self.condition_initialized = pod.get('conditions', {}).get('Initialized', '').startswith('True')
        self.condition_pod_scheduled = pod.get('conditions', {}).get('PodScheduled', '').startswith('True')
        self.condition_ready = pod.get('conditions', {}).get('Ready', '').startswith('True')
        self.has_container_crash_loop = False
        self.has_container_error = False
        for container_name, container_statuses in pod.get('containerStatuses', {}).items():
            if container_statuses.get('state', {}).get('reason') == 'Error':
                self.has_container_error = True
            if container_statuses.get('state', {}).get('reason') == 'CrashLoopBackOff':
                self.has_container_crash_loop = True


class HealthItemDeploymentConditions:

    def __init__(self, health, name):
        self.deployments = deployments = health.get('deployments', {}).get(name, {}).get('deployments', [])
        self.pods = pods = health.get('deployments', {}).get(name, {}).get('pods', [])
        if len(deployments) != 1:
            self.deployment = None
        else:
            self.deployment = deployment = deployments[0]
            self.deployment_progressing = deployment.get('conditions', {}).get('Progressing', '').startswith('True')
            self.deployment_available = deployment.get('conditions', {}).get('Available', '').startswith('True')
        self.pods_conditions = []
        self.has_pod_error = False
        self.has_pod_crash_loop = False
        self.has_pod_pending = False
        for pod in pods:
            pod_conditions = HealthItemPodConditions(pod)
            self.pods_conditions.append(pod_conditions)
            if pod_conditions.phase_pending:
                self.has_pod_pending = True
            if pod_conditions.has_container_crash_loop:
                self.has_pod_crash_loop = True
            if pod_conditions.has_container_error:
                self.has_pod_error = True


class HealthItemConditions:

    def __init__(self, item):
        self.datetime = item['datetime']
        self.health = health = item['item']
        self.deleted = bool(health.get('__deleted'))
        if not self.deleted:
            self.ready = bool(health.get('is_ready'))
            self.namespace_active = health.get('namespace', {}).get('phase') == 'Active'
            self.namespace_terminating = health.get('namespace', {}).get('phase') == 'Terminating'
            self.logger = HealthItemDeploymentConditions(health, 'logger')
            self.external_scaler = HealthItemDeploymentConditions(health, 'external-scaler')
            self.nginx = HealthItemDeploymentConditions(health, 'nginx')
            self.server = HealthItemDeploymentConditions(health, 'server')
            self.unknown = HealthItemDeploymentConditions(health, 'unknown')
            self.has_pod_crash_loop = False
            self.has_pod_error = False
            self.has_pod_pending = False
            self.has_missing_pods = False
            self.has_unknown_pods = False
            for name in ['logger', 'external_scaler', 'nginx', 'server', 'unknown']:
                deployment_conditions: HealthItemDeploymentConditions = getattr(self, name)
                if deployment_conditions.has_pod_error:
                    self.has_pod_error = True
                if deployment_conditions.has_pod_crash_loop:
                    self.has_pod_crash_loop = True
                if deployment_conditions.has_pod_pending:
                    self.has_pod_pending = True
                if name == 'unknown':
                    if len(deployment_conditions.pods) > 0:
                        self.has_unknown_pods = True
                elif len(deployment_conditions.pods) < 1:
                    self.has_missing_pods = True


class StateDuration:

    def __init__(self):
        self.first_dt = None
        self.last_dt = None
        self.stop_looking = False

    def first(self, dt):
        self.first_dt = self.last_dt = dt

    def next(self, state, dt):
        if self.last_dt and not self.stop_looking:
            if state:
                self.last_dt = dt
            else:
                self.stop_looking = True

    def total_seconds(self):
        if self.first_dt and self.last_dt:
            return (self.first_dt - self.last_dt).total_seconds()
        else:
            return None


def get_worker_conditions(worker_id):
    first_item_conditions = None
    is_first_pod_error_crash_loop = False
    pending_pod_state_duration = StateDuration()
    namespace_terminating_state_duration = StateDuration()
    has_unknown_pods = False
    has_missing_pods_state_duration = StateDuration()
    for item_conditions in map(HealthItemConditions, common.local_storage_json_last_items_iterator('workers_checker/health/{}'.format(worker_id))):
        if not item_conditions.deleted:
            pod_error_crash_loop = item_conditions.has_pod_error or item_conditions.has_pod_crash_loop
            pod_pending = item_conditions.has_pod_pending
            namespace_terminating = item_conditions.namespace_terminating
            has_missing_pods = item_conditions.has_missing_pods
            if first_item_conditions is None:
                first_item_conditions = item_conditions
                if item_conditions.has_unknown_pods:
                    has_unknown_pods = True
                if pod_error_crash_loop:
                    is_first_pod_error_crash_loop = True
                if pod_pending:
                    pending_pod_state_duration.first(item_conditions.datetime)
                if namespace_terminating:
                    namespace_terminating_state_duration.first(item_conditions.datetime)
                if has_missing_pods:
                    has_missing_pods_state_duration.first(item_conditions.datetime)
            else:
                pending_pod_state_duration.next(pod_pending, item_conditions.datetime)
                namespace_terminating_state_duration.next(namespace_terminating, item_conditions.datetime)
                has_missing_pods_state_duration.next(has_missing_pods, item_conditions.datetime)
    return {
        'pod_pending_seconds': pending_pod_state_duration.total_seconds(),
        'pod_error_crash_loop': is_first_pod_error_crash_loop,
        'namespace_terminating_seconds': namespace_terminating_state_duration.total_seconds(),
        'has_missing_pods_seconds': has_missing_pods_state_duration.total_seconds(),
        'has_unknown_pods': has_unknown_pods
    }


def get_worker_conditions_alert(worker_conditions):
    pod_pending_seconds = round(worker_conditions.get('pod_pending_seconds') or 0)
    pod_error_crash_loop = bool(worker_conditions.get('pod_error_crash_loop'))
    namespace_terminating_seconds = round(worker_conditions.get('namespace_terminating_seconds') or 0)
    has_missing_pods_seconds = int(worker_conditions.get('has_missing_pods_seconds') or 0)
    has_unknown_pods = bool(worker_conditions.get('has_unknown_pods'))
    messages = []
    if pod_pending_seconds >= config.WORKERS_CHECKER_ALERT_POD_PENDING_SECONDS:
        messages.append('pod is pending for {} seconds'.format(pod_pending_seconds))
    if pod_error_crash_loop:
        messages.append('pod has error or crash looping')
    if namespace_terminating_seconds:
        messages.append('namespace is terminating for {} seconds'.format(namespace_terminating_seconds))
    if has_missing_pods_seconds >= config.WORKERS_CHECKER_ALERT_POD_MISSING_SECONDS:
        messages.append('pod is missing for {} seconds'.format(has_missing_pods_seconds))
    if has_unknown_pods:
        messages.append('namespace has unknown pods')
    return ', '.join(messages) if len(messages) > 0 else None


def send_worker_conditions_alert(worker_id, worker_conditions, domains_config: DomainsConfig):
    alert = get_worker_conditions_alert(worker_conditions)
    if alert:
        alert = 'workers_checker ({}): {}'.format(worker_id, alert)
        logs.alert(domains_config, alert)


def send_worker_conditions_metrics(worker_id, worker_conditions, metrics: WorkersCheckerMetrics):
    if worker_conditions.get('pod_pending_seconds'):
        metrics.observe_state(worker_id, 'pod_pending')
    if worker_conditions.get('pod_error_crash_loop'):
        metrics.observe_state(worker_id, 'pod_error_crash_loop')
    if worker_conditions.get('namespace_terminating_seconds'):
        metrics.observe_state(worker_id, 'namespace_terminating')
    if worker_conditions.get('has_missing_pods_seconds'):
        metrics.observe_state(worker_id, 'has_missing_pods')
    if worker_conditions.get('has_unknown_pods'):
        metrics.observe_state(worker_id, 'has_unknown_pods')


class WorkersCheckerMultiprocessor(multiprocessor.Multiprocessor):

    def _init(self, domains_config, metrics, deployments_manager):
        self.domains_config = domains_config
        self.metrics = metrics
        self.deployments_manager = deployments_manager
        if not self.domains_config:
            self.domains_config = DomainsConfig()
        if not self.metrics:
            self.metrics = WorkersCheckerMetrics()
        if not self.deployments_manager:
            self.deployments_manager = DeploymentsManager()

    def _run_async(self, worker_id, now=None):
        assert now is None, 'cannot set now for async process'
        cmd = [
            'cwm-worker-operator', 'workers-checker', 'process_worker',
            '--worker-id', worker_id
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run_sync(self, worker_id, now=None):
        return process_worker(worker_id, self.domains_config, self.deployments_manager, now=now)

    def _get_process_key(self, worker_id, now=None):
        return worker_id

    def _handle_process_response(self, worker_id, worker_conditions):
        if worker_conditions:
            send_worker_conditions_alert(worker_id, worker_conditions, self.domains_config)
            send_worker_conditions_metrics(worker_id, worker_conditions, self.metrics)


def run_single_iteration(
        domains_config: DomainsConfig, deployments_manager: DeploymentsManager, is_async=False, now=None,
        metrics: WorkersCheckerMetrics = None, **_
):
    multiprocessor = WorkersCheckerMultiprocessor(config.WORKERS_CHECKER_MAX_PARALLEL_DEPLOY_PROCESSES if is_async else 1)
    multiprocessor.init(domains_config, metrics, deployments_manager)
    for worker_id in get_worker_ids(deployments_manager, domains_config):
        multiprocessor.process(worker_id, now=now)
    multiprocessor.finalize()


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="workers_checker",
        sleep_time_between_iterations_seconds=config.WORKERS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager,
        run_single_iteration_extra_kwargs={'is_async': True},
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_WORKERS_CHECKER,
        metrics_class=WorkersCheckerMetrics,
    ).start(
        once=once,
        with_prometheus=False
    )
