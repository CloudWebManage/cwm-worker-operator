"""
Cleanup Redis keys
"""
from collections import defaultdict

from cwm_worker_operator import config, common, logs
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def cleanup_hostname_error(domains_config: DomainsConfig, hostname, stats):
    last_deployment_flow_time = domains_config.keys.hostname_last_deployment_flow_time.get(hostname)
    if (
            domains_config.keys.hostname_error.get(hostname) in [
                domains_config.WORKER_ERROR_FAILED_TO_DEPLOY.encode(),
                domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT.encode()
            ] and (
                not last_deployment_flow_time
                or (common.now() - last_deployment_flow_time).total_seconds() > config.REDIS_CLEANER_DELETE_FAILED_TO_DEPLOY_HOSTNAME_ERROR_MIN_SECONDS
            )
    ):
        worker_id = domains_config.keys.hostname_last_deployment_flow_worker_id.get(hostname)
        if worker_id and not domains_config.is_worker_available(worker_id.decode()):
            # none of the worker hostname are available
            # we can safely delete all worker keys to force a retry on next request
            domains_config.del_worker_keys(worker_id, with_deployment_flow=False)
            domains_config.del_worker_hostname_keys(hostname, with_deployment_flow=False)
            stats['hostname_error_failed_deploy_deleted'] += 1
            return
    handle_hostname_error_any(domains_config, hostname, stats, last_deployment_flow_time)


def handle_hostname_error_any(domains_config: DomainsConfig, hostname, stats, last_deployment_flow_time='-'):
    if last_deployment_flow_time == '-':
        last_deployment_flow_time = domains_config.keys.hostname_last_deployment_flow_time.get(hostname)
    if (
            not last_deployment_flow_time
            or (common.now() - last_deployment_flow_time).total_seconds() > config.REDIS_CLEANER_DELETE_ANY_HOSTNAME_ERROR_MIN_SECONDS
    ):
        # here we handle any other error with a longer time since last deployment flow action
        # for these cases we do a full deletion of all hostname keys
        stats['hostname_error_any_deleted'] += 1
        domains_config.del_worker_hostname_keys(hostname)


def run_single_iteration(domains_config: DomainsConfig, **_):
    stats = defaultdict(int)
    for hostname in domains_config.keys.hostname_error.iterate_prefix_key_suffixes():
        cleanup_hostname_error(domains_config, hostname, stats)
    for hostname in domains_config.keys.hostname_error_attempt_number.iterate_prefix_key_suffixes():
        handle_hostname_error_any(domains_config, hostname, stats)
    if len(stats) > 0:
        logs.debug('', debug_verbosity=2, stats=dict(stats))


def start_daemon(once=False, domains_config=None):
    Daemon(
        name="redis_cleaner",
        sleep_time_between_iterations_seconds=config.REDIS_CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration
    ).start(
        once=once,
        with_prometheus=False
    )
