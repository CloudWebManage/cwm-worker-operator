"""
Checks health of NAS servers mounting from worker nodes

It iterates over all cluster worker nodes and mounts each NAS server
"""
from cwm_worker_operator import config
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def run_single_iteration(domains_config: DomainsConfig, deployments_manager, **_):
    for node in deployments_manager.iterate_cluster_nodes():
        if node['is_worker']:
            for nas_ip, is_healthy in deployments_manager.check_node_nas(node['name']).items():
                domains_config.keys.node_nas_is_healthy.set('{}:{}'.format(node['name'], nas_ip), is_healthy)
                domains_config.keys.node_nas_last_check.set('{}:{}'.format(node['name'], nas_ip))


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
