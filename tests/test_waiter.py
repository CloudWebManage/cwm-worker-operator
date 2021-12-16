import pytz
import datetime

from cwm_worker_operator import waiter, config, common, deployment_flow_manager


def assert_domain_waiter_metrics(waiter_metrics, observation):
    assert len(waiter_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in waiter_metrics.observations]), waiter_metrics.observations


def test_invalid_volume_config(domains_config, waiter_metrics, deployments_manager):
    config.PROMETHEUS_METRICS_WITH_IDENTIFIER = False
    worker_id = 'invalid.volume.config'
    domains_config.keys.worker_ready_for_deployment.set(worker_id, '')
    domains_config.keys.worker_waiting_for_deployment_complete.set(worker_id, '')
    domains_config.keys.volume_config.set(worker_id, '{}')
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, last_deployment_flow_time_key]) == {
        volume_config_key: '',
        last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_ERROR
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache', ',failed_to_get_volume_config']
    assert len(deployments_manager.calls) == 0


def test_deployment_not_ready(domains_config, waiter_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    domains_config.keys.worker_ready_for_deployment.set(worker_id, '')
    domains_config.keys.worker_waiting_for_deployment_complete.set(worker_id, '')
    deployments_manager.namespace_deployment_type_is_ready['{}-minio'.format(namespace_name)] = False
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    waiting_for_deployment_key = domains_config.keys.worker_waiting_for_deployment_complete._(worker_id)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key]) == {
        waiting_for_deployment_key: '',
        volume_config_key: '',
        ready_for_deployment_key: ''
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache']
    assert deployments_manager.calls == [('is_ready', [namespace_name, 'minio', False])]


def test_deployment_not_ready_timeout(domains_config, waiter_metrics, deployments_manager):
    config.PROMETHEUS_METRICS_WITH_IDENTIFIER = False
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    domains_config.keys.worker_waiting_for_deployment_complete.set(worker_id, '')
    deployments_manager.namespace_deployment_type_is_ready['{}-minio'.format(namespace_name)] = False
    domains_config.keys.worker_ready_for_deployment.set(worker_id, (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)).strftime("%Y%m%dT%H%M%S.%f"))
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_error_key = domains_config.keys.hostname_error._(hostname)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    hostname_last_deployment_flow_action_key = domains_config.keys.hostname_last_deployment_flow_action._(hostname)
    hostname_last_deployment_flow_time_key = domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    hostname_last_deployment_flow_worker_id_key = domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key, last_deployment_flow_time_key,
        hostname_last_deployment_flow_time_key
    ]) == {
        hostname_error_key: 'TIMEOUT_WAITING_FOR_DEPLOYMENT',
        volume_config_key: '',
        last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_ERROR,
        hostname_last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_ERROR,
        hostname_last_deployment_flow_worker_id_key: worker_id,
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache', ',timeout']
    assert deployments_manager.calls == [('is_ready', [namespace_name, 'minio', False])]


def test_deployment_ready(domains_config, waiter_metrics, deployments_manager):
    config.PROMETHEUS_METRICS_WITH_IDENTIFIER = False
    config.WAITER_VERIFY_WORKER_ACCESS = True
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    internal_hostname = 'internal.hostname'
    domains_config.keys.worker_ready_for_deployment.set(worker_id, '')
    domains_config.keys.worker_waiting_for_deployment_complete.set(worker_id, '')
    deployments_manager.namespace_deployment_type_is_ready['{}-minio'.format(namespace_name)] = True
    deployments_manager.namespace_deployment_type_hostname['{}-minio'.format(namespace_name)] = internal_hostname
    deployments_manager.hostname_verify_worker_access[internal_hostname] = True
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_available_key = domains_config.keys.hostname_available._(hostname)
    hostname_ingress_hostname_key = domains_config.keys.hostname_ingress_hostname._(hostname)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    hostname_last_deployment_flow_action_key = domains_config.keys.hostname_last_deployment_flow_action._(hostname)
    hostname_last_deployment_flow_time_key = domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    hostname_last_deployment_flow_worker_id_key = domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key, last_deployment_flow_time_key,
        hostname_last_deployment_flow_time_key
    ]) == {
        hostname_available_key: '',
        hostname_ingress_hostname_key: '"{}"'.format(internal_hostname),
        volume_config_key: '',
        last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_AVAILABLE,
        hostname_last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_AVAILABLE,
        hostname_last_deployment_flow_worker_id_key: worker_id,
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache', ',success']
    print(deployments_manager.calls)
    assert len(deployments_manager.calls) == 3
    assert deployments_manager.calls[0] == ('is_ready', [namespace_name, 'minio', False])
    assert deployments_manager.calls[1] == ('get_hostname', [namespace_name, 'minio'])
    assert deployments_manager.calls[2][0] == 'verify_worker_access'
    assert deployments_manager.calls[2][1][0] == internal_hostname
    assert deployments_manager.calls[2][1][1]['worker_id'] == worker_id


def test_wait_for_error(domains_config, waiter_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    domains_config.set_worker_ready_for_deployment(worker_id)
    domains_config.set_worker_waiting_for_deployment(worker_id, wait_for_error=True)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    waiting_for_deployment_key = domains_config.keys.worker_waiting_for_deployment_complete._(worker_id)
    ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    hostname_last_deployment_flow_action_key = domains_config.keys.hostname_last_deployment_flow_action._(hostname)
    hostname_last_deployment_flow_time_key = domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    hostname_last_deployment_flow_worker_id_key = domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname)
    # 1st iteration - no action because not enough time passed since start_time
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, ready_for_deployment_key]) == {
        waiting_for_deployment_key: 'error',
        volume_config_key: '',
        ready_for_deployment_key: '',
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache']
    assert len(deployments_manager.calls) == 0
    # 2nd attempt - set start_time in the past so it will timeout and allow to retry deployment
    domains_config.keys.worker_ready_for_deployment.set(worker_id, (common.now() - datetime.timedelta(minutes=5)).strftime("%Y%m%dT%H%M%S.%f"))
    waiter_metrics.observations = []
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key, ready_for_deployment_key, last_deployment_flow_time_key,
        hostname_last_deployment_flow_time_key
    ]) == {
        volume_config_key: '',
        ready_for_deployment_key: '',
        last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_ERROR_COMPLETE,
        hostname_last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_ERROR_COMPLETE,
        hostname_last_deployment_flow_worker_id_key: worker_id,
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache']
    assert len(deployments_manager.calls) == 0


def test_minimal_check(domains_config, waiter_metrics, deployments_manager):
    config.PROMETHEUS_METRICS_WITH_IDENTIFIER = False
    config.WAITER_VERIFY_WORKER_ACCESS = False
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl={
        'token': 'TOKEN',
        'payload': 'PAYLOAD'
    })
    internal_hostname = 'internal.hostname'
    domains_config.keys.worker_ready_for_deployment.set(worker_id, '')
    domains_config.keys.worker_waiting_for_deployment_complete.set(worker_id, '')
    deployments_manager.namespace_deployment_type_is_ready['{}-minio-minimal'.format(namespace_name)] = True
    deployments_manager.namespace_deployment_type_hostname['{}-minio'.format(namespace_name)] = internal_hostname
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_available_key = domains_config.keys.hostname_available._(hostname)
    hostname_ingress_hostname_key = domains_config.keys.hostname_ingress_hostname._(hostname)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    hostname_last_deployment_flow_action_key = domains_config.keys.hostname_last_deployment_flow_action._(hostname)
    hostname_last_deployment_flow_time_key = domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    hostname_last_deployment_flow_worker_id_key = domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key, last_deployment_flow_time_key,
        hostname_last_deployment_flow_time_key
    ]) == {
        hostname_available_key: '',
        hostname_ingress_hostname_key: '"{}"'.format(internal_hostname),
        volume_config_key: '',
        last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_AVAILABLE,
        hostname_last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_action_key: deployment_flow_manager.WAITER_WORKER_AVAILABLE,
        hostname_last_deployment_flow_worker_id_key: worker_id,
    }
    assert [','.join(o['labels']) for o in waiter_metrics.observations] == [',success_cache', ',success']
    assert len(deployments_manager.calls) == 2
    assert deployments_manager.calls[0] == ('is_ready', [namespace_name, 'minio', True])
    assert deployments_manager.calls[1] == ('get_hostname', [namespace_name, 'minio'])
