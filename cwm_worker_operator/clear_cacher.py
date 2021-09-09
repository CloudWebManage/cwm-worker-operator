"""
Handles requests for Nginx clear cache from users
"""
import traceback

from cwm_worker_operator import config
from cwm_worker_operator import common
from cwm_worker_operator import logs
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def clear_cache_node(node, domains_config, deployments_manager):
    for namespace_name, pod_name in deployments_manager.iterate_minio_nginx_pods_on_node(node['name']):
        try:
            worker_id = common.get_worker_id_from_namespace_name(namespace_name)
            volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
            requested_clear_cache = volume_config.clear_cache
            if requested_clear_cache:
                last_clear_cache = domains_config.get_worker_last_clear_cache(worker_id)
                if not last_clear_cache or last_clear_cache < requested_clear_cache:
                    now = common.now()
                    deployments_manager.pod_exec(namespace_name, pod_name, 'bash', '-c', 'rm -rf /var/cache/nginx/minio/cache/*')
                    domains_config.set_worker_last_clear_cache(worker_id, now)
        except Exception as e:
            logs.debug_info("exception: {}".format(e), namespace_name=namespace_name, pod_name=pod_name)
            if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                traceback.print_exc()


def run_single_iteration(domains_config: DomainsConfig, deployments_manager, **_):
    for node in deployments_manager.iterate_cluster_nodes():
        if node['is_worker']:
            clear_cache_node(node, domains_config, deployments_manager)


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="clear_cacher",
        sleep_time_between_iterations_seconds=config.CLEAR_CACHER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=False
    )
