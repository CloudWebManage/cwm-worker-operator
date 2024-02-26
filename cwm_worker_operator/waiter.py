"""
Waits for deployed workers to be available
"""
import traceback
import subprocess

from cwm_worker_operator import metrics
from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator import domains_config
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.deployment_flow_manager import WaiterDeploymentFlowManager
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator.multiprocessor import Multiprocessor


def _check_for_deployment_complete(domains_config, deployments_manager, waiter_metrics, start_time, log_kwargs, namespace_name, flow_manager, worker_id, volume_config):
    # has_hostnames_without_cert_but_with_challenge = False
    # check_hostname_challenge = None
    # for hostname in volume_config.hostnames:
    #     if hostname not in volume_config.hostname_certs and hostname in volume_config.hostname_challenges:
    #         has_hostnames_without_cert_but_with_challenge = True
    #         check_hostname_challenge = {
    #             'host': hostname,
    #             **volume_config.hostname_challenges[hostname]
    #         }
    #         break
    if deployments_manager.is_ready(namespace_name, "minio"):  # , minimal_check=has_hostnames_without_cert_but_with_challenge):
        # internal_hostname = deployments_manager.get_hostname(namespace_name, "minio")
        internal_hostname = {
            'http': f'nginx.{namespace_name}.svc.cluster.local',
            'https': f'nginx.{namespace_name}.svc.cluster.local'
        }
        ok = True
        # if config.WAITER_VERIFY_WORKER_ACCESS:
        #     ok = deployments_manager.verify_worker_access(internal_hostname, log_kwargs, check_hostname_challenge=check_hostname_challenge)
        if ok:
            flow_manager.set_worker_available(worker_id, internal_hostname)
            if waiter_metrics:
                waiter_metrics.deployment_success(worker_id, start_time)
            logs.debug_info("Success", **log_kwargs)
            return
    if (common.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS:
        flow_manager.set_worker_error(worker_id, domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
        if waiter_metrics:
            waiter_metrics.deployment_timeout(worker_id, start_time)
        logs.debug_info("timeout", **log_kwargs)


def _check_for_error(domains_config, start_time, log_kwargs, flow_manager, worker_id):
    if (common.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_ERROR_MAX_SECONDS:
        flow_manager.set_worker_wait_for_error_complete(worker_id)
        logs.debug_info("wait for error complete", **log_kwargs)


def check_deployment_complete(worker_id, domains_config=None, waiter_metrics=None, deployments_manager=None, flow_manager=None):
    if not domains_config:
        domains_config = DomainsConfig()
    if not deployments_manager:
        deployments_manager = DeploymentsManager()
    if not flow_manager:
        flow_manager = WaiterDeploymentFlowManager(domains_config)
    start_time = domains_config.get_worker_ready_for_deployment_start_time(worker_id)
    check_for_error = domains_config.keys.worker_waiting_for_deployment_complete.get(worker_id).decode() == 'error'
    log_kwargs = {"worker_id": worker_id, "start_time": start_time, "check_for_error": check_for_error}
    # this log occurs on every iteration of waiter, so it should be at debug verbosity 10 otherwise there is a flood of logs
    logs.debug("Start check_deployment_complete", debug_verbosity=10, **log_kwargs)
    try:
        volume_config, namespace_name = domains_config.get_volume_config_namespace_from_worker_id(waiter_metrics, worker_id)
        if not namespace_name:
            if waiter_metrics:
                waiter_metrics.failed_to_get_volume_config(worker_id, start_time)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            flow_manager.set_worker_error(worker_id, domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
            return True
        if check_for_error:
            _check_for_error(domains_config, start_time, log_kwargs, flow_manager, worker_id)
        else:
            _check_for_deployment_complete(domains_config, deployments_manager, waiter_metrics, start_time, log_kwargs, namespace_name, flow_manager, worker_id, volume_config)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        if waiter_metrics:
            waiter_metrics.exception(worker_id, start_time)
    return True


class WaiterMultiprocessor(Multiprocessor):

    def _run_async(self, worker_id, domains_config, waiter_metrics, deployments_manager, flow_manager):
        cmd = [
            'cwm-worker-operator', 'waiter', 'check_deployment_complete',
            '--worker-id', worker_id
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run_sync(self, worker_id, domains_config, waiter_metrics, deployments_manager, flow_manager):
        check_deployment_complete(worker_id, domains_config, waiter_metrics, deployments_manager, flow_manager)

    def _get_process_key(self, worker_id, *args, **kwargs):
        return worker_id


def run_single_iteration(domains_config: domains_config.DomainsConfig, metrics, deployments_manager, is_async=False, **_):
    multiprocessor = WaiterMultiprocessor(config.WAITER_MAX_PARALLEL_DEPLOY_PROCESSES if is_async else 1)
    waiter_metrics = metrics
    flow_manager = WaiterDeploymentFlowManager(domains_config)
    worker_ids_waiting_for_deployment_complete = set(flow_manager.iterate_worker_ids_waiting_for_deployment_complete())
    for worker_id in worker_ids_waiting_for_deployment_complete:
        multiprocessor.process(worker_id, domains_config, waiter_metrics, deployments_manager, flow_manager)
    multiprocessor.finalize()


def start_daemon(once=False, with_prometheus=True, waiter_metrics=None, domains_config=None):
    Daemon(
        name='waiter',
        sleep_time_between_iterations_seconds=config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.WaiterMetrics,
        domains_config=domains_config,
        metrics=waiter_metrics,
        run_single_iteration_callback=run_single_iteration,
        run_single_iteration_extra_kwargs={'is_async': True},
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_WAITER
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
