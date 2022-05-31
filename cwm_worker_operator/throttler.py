"""
Throttle workers which use too much resources
"""
import datetime

from cwm_worker_operator import config, common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def _throttle_start(domains_config, now, worker_id,
                    num_requests_total, last_throttle_check_num_requests_total,
                    last_throttle_check_datetime):
    throttle_expiry = now + datetime.timedelta(seconds=config.THROTTLER_THROTTLE_PERIOD_SECONDS)
    domains_config.keys.worker_throttled_expiry.set(worker_id, throttle_expiry)
    domains_config.set_worker_error(worker_id, domains_config.WORKER_ERROR_THROTTLED)
    common.local_storage_json_last_items_append(
        f'throttler/started/{worker_id}',
        {
            'num_requests_total': num_requests_total,
            'throttle_expiry': throttle_expiry.strftime('%Y-%m-%d %H:%M:%S'),
            'last_throttle_check': {
                'num_requests_total': last_throttle_check_num_requests_total,
                'dt': last_throttle_check_datetime.strftime('%Y-%m-%d %H:%M:%S')
            }
        },
        max_items=100,
        now_=now
    )


def _throttle_stop(domains_config, worker_id):
    domains_config.del_worker_keys(worker_id, with_throttle=True)


def check_worker_throttle(domains_config, worker_id, now=None):
    if now is None:
        now = common.now()
    last_throttle_check = domains_config.keys.worker_last_throttle_check.get(worker_id)
    if last_throttle_check and last_throttle_check.get('t'):
        last_throttle_check_datetime = common.strptime(last_throttle_check['t'], '%Y-%m-%d %H:%M:%S')
        last_throttle_check_num_requests_total = int(last_throttle_check.get('r') or 0)
        seconds_since_last_throttle_check = (now - last_throttle_check_datetime).total_seconds()
    else:
        last_throttle_check_num_requests_total = None
        seconds_since_last_throttle_check = None
        last_throttle_check_datetime = None
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
                _throttle_start(domains_config, now, worker_id,
                                num_requests_total, last_throttle_check_num_requests_total,
                                last_throttle_check_datetime)


def check_worker_throttle_expiry(domains_config, worker_id, now=None):
    if now is None:
        now = common.now()
    expiry = domains_config.keys.worker_throttled_expiry.get(worker_id)
    if expiry and now >= expiry:
        _throttle_stop(domains_config, worker_id)


def run_single_iteration(domains_config: DomainsConfig, now=None, **_):
    checked_worker_ids = set()
    for _, worker_id in domains_config.iterate_ingress_hostname_worker_ids():
        if worker_id not in checked_worker_ids:
            checked_worker_ids.add(worker_id)
            check_worker_throttle(domains_config, worker_id, now)
    for worker_id in domains_config.keys.worker_throttled_expiry.iterate_prefix_key_suffixes():
        check_worker_throttle_expiry(domains_config, worker_id, now)


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
