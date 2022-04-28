"""
Throttle workers which use too much resources
"""
import datetime

from cwm_worker_operator import config, common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def check_worker_throttle(domains_config, worker_id):
    last_throttle_check = domains_config.keys.worker_last_throttle_check.get(worker_id)
    now = common.now()
    if last_throttle_check and last_throttle_check.get('t'):
        last_throttle_check_datetime = common.strptime(last_throttle_check['t'], '%Y-%m-%d %H:%M:%S')
        last_throttle_check_num_requests_total = int(last_throttle_check.get('r') or 0)
        seconds_since_last_throttle_check = (now - last_throttle_check_datetime).total_seconds()
    else:
        last_throttle_check_num_requests_total = None
        seconds_since_last_throttle_check = None
    if not seconds_since_last_throttle_check or seconds_since_last_throttle_check >= config.THROTTLER_CHECK_TTL_SECONDS:
        deployment_api_metrics = domains_config.get_deployment_api_metrics(common.get_namespace_name_from_worker_id(worker_id))
        num_requests_total = sum([int(deployment_api_metrics.get(key) or 0) for key in ['num_requests_in', 'num_requests_misc', 'num_requests_out']])
        domains_config.keys.worker_last_throttle_check.set(worker_id, {
            't': now.strftime('%Y-%m-%d %H:%M:%S'),
            'r': num_requests_total
        })
        if last_throttle_check_num_requests_total is not None:
            num_requests_since_last_throttle_check = num_requests_total - last_throttle_check_num_requests_total
            if num_requests_since_last_throttle_check >= config.THROTTLER_THROTTLE_MAX_REQUESTS:
                domains_config.keys.worker_throttled_expiry.set(
                    worker_id,
                    now + datetime.timedelta(seconds=config.THROTTLER_THROTTLE_PERIOD_SECONDS)
                )
                domains_config.set_worker_error(worker_id, domains_config.WORKER_ERROR_THROTTLED)


def check_worker_throttle_expiry(domains_config, worker_id):
    now = common.now()
    expiry = domains_config.keys.worker_throttled_expiry.get(worker_id)
    if expiry and now >= expiry:
        domains_config.del_worker_keys(worker_id, with_throttle=True)


def run_single_iteration(domains_config: DomainsConfig, **_):
    for hostname in domains_config.keys.hostname_available.iterate_prefix_key_suffixes():
        worker_id = domains_config.keys.volume_config_hostname_worker_id.get(hostname)
        if worker_id:
            check_worker_throttle(domains_config, worker_id)
    for worker_id in domains_config.keys.worker_throttled_expiry.iterate_prefix_key_suffixes():
        check_worker_throttle_expiry(domains_config, worker_id)


def start_daemon(once=False, domains_config=None):
    Daemon(
        name="throttler",
        sleep_time_between_iterations_seconds=config.THROTTLER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
    ).start(
        once=once,
        with_prometheus=False
    )
