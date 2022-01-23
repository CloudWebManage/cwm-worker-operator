"""
Check workers and update status in Redis and local storage
"""
import json
import traceback
import subprocess

from cwm_worker_operator import config, common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator.multiprocessor import Multiprocessor
from cwm_worker_operator.common import local_storage_json_last_items_append


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
                   deployments_manager: DeploymentsManager = None):
    if not domains_config:
        domains_config = DomainsConfig()
    if not deployments_manager:
        deployments_manager = DeploymentsManager()
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
            local_storage_json_last_items_append('workers_checker/health/{}'.format(worker_id),
                                                 health, max_items=100)
        else:
            domains_config.keys.worker_health.delete(worker_id)
    return True


class WorkersCheckerMultiprocessor(Multiprocessor):

    def _run_async(self, domains_config, deployments_manager, worker_id):
        cmd = [
            'cwm-worker-operator', 'workers-checker', 'process_worker',
            '--worker-id', worker_id
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run_sync(self, domains_config, deployments_manager, worker_id):
        process_worker(worker_id, domains_config, deployments_manager)

    def _get_process_key(self, domains_config, deployments_manager, worker_id):
        return worker_id


def run_single_iteration(domains_config: DomainsConfig, deployments_manager: DeploymentsManager, is_async=False, **_):
    multiprocessor = WorkersCheckerMultiprocessor(config.WORKERS_CHECKER_MAX_PARALLEL_DEPLOY_PROCESSES if is_async else 1)
    for worker_id in get_worker_ids(deployments_manager, domains_config):
        multiprocessor.process(domains_config, deployments_manager, worker_id)
    multiprocessor.finalize()


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="workers_checker",
        sleep_time_between_iterations_seconds=config.WORKERS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager,
        run_single_iteration_extra_kwargs={'is_async': True},
    ).start(
        once=once,
        with_prometheus=False
    )
