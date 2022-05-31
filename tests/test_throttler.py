import os
import json
import shutil
import datetime

from cwm_worker_operator import throttler, common, config


def set_ingress_hostname(domains_config, hostname, worker_id):
    domains_config.keys.hostname_ingress_hostname.set(hostname, json.dumps({
        'http': f'minio-nginx.{common.get_namespace_name_from_worker_id(worker_id)}.svc.cluster.local',
        'https': f'minio-nginx.{common.get_namespace_name_from_worker_id(worker_id)}.svc.cluster.local',
    }))


def set_ingress_hostname_invalid(domains_config, hostname):
    domains_config.keys.hostname_ingress_hostname.set(hostname, json.dumps({}))


def test_throttler(domains_config):
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, 'throttler'), ignore_errors=True)

    # no hostnames - no actions performed
    throttler.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values(blank_keys=[]) == {}

    # an available hostname but which doesn't have any related worker_id - will not be processed
    hostname_no_worker_id = 'hostname.available.no.worker.id'
    set_ingress_hostname_invalid(domains_config, hostname_no_worker_id)

    # a valid hostname available with related worker id - will be processed by the throttler
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    set_ingress_hostname(domains_config, hostname, worker_id)

    now = common.now()
    blank_keys = [
        domains_config.keys.worker_last_throttle_check._(worker_id),
        domains_config.keys.volume_config._(worker_id),
        domains_config.keys.hostname_ingress_hostname._(hostname),
        domains_config.keys.hostname_ingress_hostname._(hostname_no_worker_id),
    ]
    expected_values = {
        domains_config.keys.hostname_ingress_hostname._(hostname): '',
        domains_config.keys.hostname_ingress_hostname._(hostname_no_worker_id): '',
        domains_config.keys.worker_last_throttle_check._(worker_id): '',
        domains_config.keys.volume_config._(worker_id): '',
    }
    # last throttle check will be updated for the valid worker hostname
    expected_last_throttle_check = {
        # date/time of the last check (now)
        't': now.strftime('%Y-%m-%d %H:%M:%S'),
        # number of requests recorded (0 - had no requests)
        'r': 0
    }
    throttler.run_single_iteration(domains_config, now=now)
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values
    assert domains_config.keys.worker_last_throttle_check.get(worker_id) == expected_last_throttle_check

    # run another iteration, 1 second later - should not perform any actions
    # because time since last check is less then THROTTLER_CHECK_TTL_SECONDS
    now = now + datetime.timedelta(seconds=1)
    throttler.run_single_iteration(domains_config, now=now)
    # keys are the same as last iteration - no actions were performed
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values
    assert domains_config.keys.worker_last_throttle_check.get(worker_id) == expected_last_throttle_check

    # set metric value less then the threshold - so it won't be throttled but will update last recorded value
    num_requests_in = config.THROTTLER_THROTTLE_MAX_REQUESTS - 100
    domains_config.keys.deployment_api_metric.set(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)),
        num_requests_in
    )
    now = now + datetime.timedelta(seconds=config.THROTTLER_CHECK_TTL_SECONDS + 1)
    expected_last_throttle_check = {
        't': now.strftime('%Y-%m-%d %H:%M:%S'),
        'r': num_requests_in
    }
    expected_values[domains_config.keys.deployment_api_metric._(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id))
    )] = str(num_requests_in)
    throttler.run_single_iteration(domains_config, now=now)
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values
    assert domains_config.keys.worker_last_throttle_check.get(worker_id) == expected_last_throttle_check

    # increase metric value beyond threshold but still different since
    # last check is below threshold so it won't be throttled
    num_requests_in += config.THROTTLER_THROTTLE_MAX_REQUESTS - 100
    domains_config.keys.deployment_api_metric.set(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)),
        num_requests_in
    )
    now = now + datetime.timedelta(seconds=config.THROTTLER_CHECK_TTL_SECONDS + 1)
    expected_last_throttle_check = {
        't': now.strftime('%Y-%m-%d %H:%M:%S'),
        'r': num_requests_in
    }
    expected_values[domains_config.keys.deployment_api_metric._(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id))
    )] = str(num_requests_in)
    throttler.run_single_iteration(domains_config, now=now)
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values
    assert domains_config.keys.worker_last_throttle_check.get(worker_id) == expected_last_throttle_check

    # increase metric value so it will be throttled
    num_requests_in += config.THROTTLER_THROTTLE_MAX_REQUESTS + 100
    domains_config.keys.deployment_api_metric.set(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)),
        num_requests_in
    )
    del expected_values[domains_config.keys.hostname_ingress_hostname._(hostname)]
    now = now + datetime.timedelta(seconds=config.THROTTLER_CHECK_TTL_SECONDS + 1)
    expected_values = {
        **expected_values,
        domains_config.keys.hostname_error._(hostname): domains_config.WORKER_ERROR_THROTTLED,
        domains_config.keys.worker_throttled_expiry._(worker_id): (now + datetime.timedelta(seconds=config.THROTTLER_THROTTLE_PERIOD_SECONDS)).strftime('%Y%m%d%H%M%S'),
        domains_config.keys.deployment_api_metric._(
            '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id))
        ): str(num_requests_in)
    }
    expected_last_throttle_check = {
        't': now.strftime('%Y-%m-%d %H:%M:%S'),
        'r': num_requests_in
    }
    throttler.run_single_iteration(domains_config, now=now)
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values
    assert domains_config.keys.worker_last_throttle_check.get(worker_id) == expected_last_throttle_check

    # increase metric value again - nothing will change because it's already throttled
    num_requests_in += config.THROTTLER_THROTTLE_MAX_REQUESTS + 100
    domains_config.keys.deployment_api_metric.set(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)),
        num_requests_in
    )
    expected_values[domains_config.keys.deployment_api_metric._(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id))
    )] = str(num_requests_in)
    now = now + datetime.timedelta(seconds=config.THROTTLER_CHECK_TTL_SECONDS + 1)
    throttler.run_single_iteration(domains_config, now=now)
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values
    assert domains_config.keys.worker_last_throttle_check.get(worker_id) == expected_last_throttle_check

    # reach the threshold expiry time - all worker keys will be deleted allowing it to be accessed again
    now = common.strptime(expected_values[domains_config.keys.worker_throttled_expiry._(worker_id)], '%Y%m%d%H%M%S')
    throttler.run_single_iteration(domains_config, now=now)
    del expected_values[domains_config.keys.hostname_error._(hostname)]
    del expected_values[domains_config.keys.worker_throttled_expiry._(worker_id)]
    del expected_values[domains_config.keys.worker_last_throttle_check._(worker_id)]
    del expected_values[domains_config.keys.volume_config._(worker_id)]
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values

    # fake another throttle to ensure local storage keeps a log of all throttles
    domains_config.keys.hostname_ingress_hostname.delete(hostname_no_worker_id)
    del expected_values[domains_config.keys.hostname_ingress_hostname._(hostname_no_worker_id)]
    set_ingress_hostname(domains_config, hostname, worker_id)
    blank_keys.append(domains_config.keys.hostname_ingress_hostname._(hostname))
    expected_values[domains_config.keys.hostname_ingress_hostname._(hostname)] = ''
    num_requests_in = 500
    domains_config.keys.deployment_api_metric.set('{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)), num_requests_in)
    expected_values[domains_config.keys.deployment_api_metric._('{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)))] = str(num_requests_in)
    now = now + datetime.timedelta(minutes=5)
    throttler.run_single_iteration(domains_config, now=now)
    now = now + datetime.timedelta(minutes=5)
    num_requests_in += 10000000
    domains_config.keys.deployment_api_metric.set(
        '{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)),
        num_requests_in
    )
    expected_values[domains_config.keys.deployment_api_metric._('{}:num_requests_in'.format(common.get_namespace_name_from_worker_id(worker_id)))] = str(num_requests_in)
    throttler.run_single_iteration(domains_config, now=now)
    blank_keys.append(domains_config.keys.worker_throttled_expiry._(worker_id))
    expected_values = {
        **expected_values,
        domains_config.keys.worker_throttled_expiry._(worker_id): '',
        domains_config.keys.worker_last_throttle_check._(worker_id): '',
        domains_config.keys.volume_config._(worker_id): ''
    }
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_values

    # check the log of throttles in local storage
    items = list(common.local_storage_json_last_items_iterator(f'throttler/started/{worker_id}'))
    assert len(items) == 2
    assert items[0] == {
        'datetime': now,
        'item': {
            'num_requests_total': 10000500,
            'throttle_expiry': (now + datetime.timedelta(seconds=config.THROTTLER_THROTTLE_PERIOD_SECONDS)).strftime('%Y-%m-%d %H:%M:%S'),
            'last_throttle_check': {
                'num_requests_total': 500,
                'dt': (now - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
            }
        }
    }
