import time

from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


def cleanup_node(node, domains_config, deployments_manager):
    with deployments_manager.node_cleanup_pod(node['name']) as node_cleanup_pod:
        for namespace_name in node_cleanup_pod.list_cache_namespaces():
            domain_name = namespace_name.replace('--', '.')
            if not domains_config.is_worker_available(domain_name) or not deployments_manager.worker_has_pod_on_node(namespace_name, node['name']):
                node_cleanup_pod.clear_cache_namespace(namespace_name)


def run_single_iteration(domains_config, deployments_manager):
    for node in deployments_manager.iterate_cluster_nodes():
        if node['is_worker'] and not node['unschedulable']:
            cleanup_node(node, domains_config, deployments_manager)


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    with logs.alert_exception_catcher(domains_config, daemon="cleaner"):
        while True:
            run_single_iteration(domains_config, deployments_manager)
            if once:
                break
            time.sleep(config.CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
