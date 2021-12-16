import datetime

from cwm_worker_operator import redis_cleaner, common, config


def test(domains_config):
    invalid_hostname = 'invalid.example.com'
    timeout_hostname = 'timeout.example.com'
    invalid_volume_zone_hostname = 'invalid-volume-zone.example.com'
    failed_to_get_volume_config_hostname = 'failed-to-get-volume-config.example.com'
    failed_to_deploy_hostname = 'failed-to-deploy.example.com'
    redis_cleaner.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values() == {}
    domains_config.keys.hostname_error.set(invalid_hostname, domains_config.WORKER_ERROR_INVALID_HOSTNAME)
    domains_config.keys.hostname_error.set(timeout_hostname, domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
    domains_config.keys.hostname_error.set(invalid_volume_zone_hostname, domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE)
    domains_config.keys.hostname_error.set(failed_to_get_volume_config_hostname, domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
    domains_config.keys.hostname_error.set(failed_to_deploy_hostname, domains_config.WORKER_ERROR_FAILED_TO_DEPLOY)
    redis_cleaner.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values() == {}


def test_last_deployment_flow(domains_config):
    hostname = 'www.example.com'
    worker_id = 'example1'
    domains_config.keys.hostname_error.set(hostname, domains_config.WORKER_ERROR_FAILED_TO_DEPLOY)
    domains_config.keys.hostname_last_deployment_flow_time.set(hostname)
    domains_config.keys.hostname_last_deployment_flow_worker_id.set(hostname, worker_id)
    redis_cleaner.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    ]) == {
        domains_config.keys.hostname_error._(hostname): domains_config.WORKER_ERROR_FAILED_TO_DEPLOY,
        domains_config.keys.hostname_last_deployment_flow_time._(hostname): '',
        domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname): worker_id
    }
    domains_config.keys.hostname_last_deployment_flow_time.set(
        hostname,
        common.now() - datetime.timedelta(
            seconds=config.REDIS_CLEANER_DELETE_FAILED_TO_DEPLOY_HOSTNAME_ERROR_MIN_SECONDS + 1
        )
    )
    redis_cleaner.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.hostname_last_deployment_flow_time._(hostname),
        domains_config.keys.volume_config._(worker_id)
    ]) == {
        domains_config.keys.hostname_last_deployment_flow_time._(hostname): '',
        domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname): worker_id
    }


def test_error_any_deletion(domains_config):
    hostname = 'www.example.com'
    domains_config.keys.hostname_error.set(hostname, domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE)
    domains_config.keys.hostname_last_deployment_flow_time.set(hostname)
    domains_config.keys.hostname_available.set(hostname, '')
    redis_cleaner.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    ]) == {
        domains_config.keys.hostname_error._(hostname): domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE,
        domains_config.keys.hostname_last_deployment_flow_time._(hostname): '',
        domains_config.keys.hostname_available._(hostname): ''
    }
    domains_config.keys.hostname_last_deployment_flow_time.set(hostname, common.now() - datetime.timedelta(seconds=config.REDIS_CLEANER_DELETE_ANY_HOSTNAME_ERROR_MIN_SECONDS + 1))
    redis_cleaner.run_single_iteration(domains_config)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    ]) == {}
