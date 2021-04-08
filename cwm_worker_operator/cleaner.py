from cwm_worker_operator import config
from cwm_worker_operator.daemon import Daemon


def cleanup_node(node, domains_config, deployments_manager):
    with deployments_manager.node_cleanup_pod(node['name']) as node_cleanup_pod:
        for namespace_name in node_cleanup_pod.list_cache_namespaces():
            domain_name = namespace_name.replace('--', '.')
            if not domains_config.is_worker_available(domain_name) or not deployments_manager.worker_has_pod_on_node(namespace_name, node['name']):
                node_cleanup_pod.clear_cache_namespace(namespace_name)


def run_single_iteration(domains_config, deployments_manager, **_):
    for node in deployments_manager.iterate_cluster_nodes():
        if node['is_worker'] and not node['unschedulable']:
            cleanup_node(node, domains_config, deployments_manager)


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="cleaner",
        sleep_time_between_iterations_seconds=config.CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=False
    )
