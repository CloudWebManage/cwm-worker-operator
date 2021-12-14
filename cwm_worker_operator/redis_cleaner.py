"""
Cleanup Redis keys
"""
from collections import defaultdict

from cwm_worker_operator import config, common, logs
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def cleanup_hostname_error(domains_config: DomainsConfig, hostname, stats):
    if domains_config.keys.hostname_error.get(hostname) in [
        # we only consider for deletion errors which have a chance to be successful at a later time
        domains_config.WORKER_ERROR_FAILED_TO_DEPLOY.encode(),
        domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT.encode()
    ]:
        last_deployment_flow_time = domains_config.keys.hostname_last_deployment_flow_time.get(hostname)
        if (
                not last_deployment_flow_time
                or (common.now() - last_deployment_flow_time).total_seconds() > config.REDIS_CLEANER_DELETE_FAILED_TO_DEPLOY_HOSTNAME_ERROR_MIN_SECONDS
        ):
            stats['hostname_error_deleted'] += 1
            domains_config.keys.hostname_error.delete(hostname)


def run_single_iteration(domains_config: DomainsConfig, **_):
    stats = defaultdict(int)
    for hostname in domains_config.keys.hostname_error.iterate_prefix_key_suffixes():
        cleanup_hostname_error(domains_config, hostname, stats)
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
