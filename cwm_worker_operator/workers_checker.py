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


def get_namespace_names(deployments_manager: DeploymentsManager, domains_config: DomainsConfig):
    namespace_names = set()
    for release in deployments_manager.iterate_all_releases():
        namespace_names.add(release['namespace'])
    for worker_id in domains_config.keys.worker_health.iterate_prefix_key_suffixes():
        namespace_names.add(common.get_namespace_name_from_worker_id(worker_id))
    for namespace_name in deployments_manager.get_worker_id_namespaces():
        namespace_names.add(namespace_name)
    return namespace_names


def process_namespace(namespace_name,
                      domains_config: DomainsConfig = None,
                      deployments_manager: DeploymentsManager = None):
    if not domains_config:
        domains_config = DomainsConfig()
    if not deployments_manager:
        deployments_manager = DeploymentsManager()
    worker_id = common.get_worker_id_from_namespace_name(namespace_name)
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

    def _run_async(self, domains_config, deployments_manager, namespace_name):
        cmd = [
            'cwm-worker-operator', 'workers-checker', 'process_namespace',
            '--namespace-name', namespace_name
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run_sync(self, domains_config, deployments_manager, namespace_name):
        process_namespace(namespace_name, domains_config, deployments_manager)

    def _get_process_key(self, domains_config, deployments_manager, namespace_name):
        return namespace_name


def run_single_iteration(domains_config: DomainsConfig, deployments_manager: DeploymentsManager, is_async=False, **_):
    multiprocessor = WorkersCheckerMultiprocessor(config.WORKERS_CHECKER_MAX_PARALLEL_DEPLOY_PROCESSES if is_async else 1)
    for namespace_name in get_namespace_names(deployments_manager, domains_config):
        multiprocessor.process(domains_config, deployments_manager, namespace_name)
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
