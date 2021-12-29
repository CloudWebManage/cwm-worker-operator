"""
Checks health of NAS servers mounting from worker nodes

It iterates over all cluster worker nodes and mounts each NAS server
"""
from cwm_worker_operator import config, common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def run_single_iteration(domains_config: DomainsConfig, deployments_manager, now=None, max_last_errors=20, **_):
    if not now:
        now = common.now()
    all_worker_node_names = set([node['name'] for node in deployments_manager.iterate_cluster_worker_nodes()])
    all_nas_ips = set()
    for node_name, nas_ip_statuses in deployments_manager.check_nodes_nas(all_worker_node_names).items():
        for nas_ip, status in nas_ip_statuses.items():
            all_nas_ips.add(nas_ip)
            domains_config.keys.node_nas_is_healthy.set('{}:{}'.format(node_name, nas_ip), status['is_healthy'])
            domains_config.keys.node_nas_last_check.set('{}:{}'.format(node_name, nas_ip))
            common.local_storage_json_set('nas_checker/status_details/{}/{}'.format(node_name, nas_ip), status)
            if not status['is_healthy']:
                common.local_storage_json_last_items_append('nas_checker/status_details/{}/{}-last-errors'.format(node_name, nas_ip), status,
                                                            now_=now, max_items=max_last_errors)
    for domains_config_key in [domains_config.keys.node_nas_is_healthy, domains_config.keys.node_nas_last_check]:
        for key in domains_config_key.iterate_prefix_key_suffixes():
            node_name, nas_ip = key.split(':')
            if node_name not in all_worker_node_names or nas_ip not in all_nas_ips:
                domains_config_key.delete('{}:{}'.format(node_name, nas_ip))


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="nas_checker",
        sleep_time_between_iterations_seconds=config.NAS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=False
    )
