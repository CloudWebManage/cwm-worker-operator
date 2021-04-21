import json
import datetime

from cwm_worker_operator import initializer
from cwm_worker_operator import config
from cwm_worker_operator import common


def assert_volume_config(domains_config, worker_id, expected_data, msg):
    volume_config = json.loads(domains_config.keys.volume_config.get(worker_id))
    assert set(volume_config.keys()) == set(['id', '__last_update', 'hostname', *expected_data.keys()]), msg
    assert volume_config['id'] == worker_id, msg
    assert isinstance(common.strptime(volume_config['__last_update'], '%Y%m%dT%H%M%S'), datetime.datetime), msg
    for key, value in expected_data.items():
        assert volume_config[key] == value, '{}: {}'.format(key, msg)


def test_initialize_invalid_volume_config(domains_config, initializer_metrics):
    hostname = 'example007.com'
    domains_config.keys.hostname_initialize.set(hostname, '')
    hostname_error_attempt_number_key = domains_config.keys.hostname_error_attempt_number._(hostname)
    hostname_initialize_key = domains_config.keys.hostname_initialize._(hostname)
    hostname_error_key = domains_config.keys.hostname_error._(hostname)
    expected_metrics_observations = []
    for i in range(1, config.WORKER_ERROR_MAX_ATTEMPTS+1):
        initializer.run_single_iteration(domains_config, initializer_metrics)
        common_expected_key_values = {
            hostname_error_attempt_number_key: str(i)
        }
        if i < config.WORKER_ERROR_MAX_ATTEMPTS:
            assert domains_config._get_all_redis_pools_values() == {
                **common_expected_key_values,
                hostname_initialize_key: ""
            }, i
        else:
            assert domains_config._get_all_redis_pools_values() == {
                **common_expected_key_values,
                hostname_error_key: "FAILED_TO_GET_VOLUME_CONFIG",
            }, i
        # "error" observations is from domains_config.cwm_api_get_volume_config
        # "failed_to_get_volume_config" is from initializer
        expected_metrics_observations += [',error', ',failed_to_get_volume_config']
    assert [','.join(o['labels']) for o in initializer_metrics.observations] == expected_metrics_observations


def test_initialize_invalid_volume_zone(domains_config, initializer_metrics):
    worker_id, hostname = 'worker1', 'invalid-zone.com'
    domains_config.keys.hostname_initialize.set(hostname, '')
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_error_key = domains_config.keys.hostname_error._(hostname)
    # set mock volume config in api with invalid zone
    domains_config._cwm_api_volume_configs['hostname:{}'.format(hostname)] = {'id': worker_id, 'hostname': hostname, 'zone': 'INVALID'}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key]) == {
        volume_config_key: "",
        hostname_error_key: 'INVALID_VOLUME_ZONE'
    }
    assert_volume_config(domains_config, worker_id, {
        'zone': 'INVALID'
    }, '')
    # success observation is for success getting volume config from api
    # invalid_volume_zone is from initializer
    assert [','.join(o['labels']) for o in initializer_metrics.observations] == [',success', ',invalid_volume_zone']


def test_initialize_valid_domain(domains_config, initializer_metrics):
    worker_id, hostname = 'worker1', 'valid-domain.com'
    domains_config.keys.hostname_initialize.set(hostname, '')
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_initialize_key = domains_config.keys.hostname_initialize._(hostname)
    worker_ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    # set mock volume config in api with valid zone
    domains_config._cwm_api_volume_configs['hostname:{}'.format(hostname)] = {'id': worker_id, 'hostname': hostname, 'zone': config.CWM_ZONE}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, worker_ready_for_deployment_key]) == {
        hostname_initialize_key: '',
        worker_ready_for_deployment_key: "",
        volume_config_key: ""
    }
    assert_volume_config(domains_config, worker_id, {
        'zone': config.CWM_ZONE
    }, '')
    assert isinstance(common.strptime(domains_config.keys.worker_ready_for_deployment.get(worker_id).decode(), '%Y%m%dT%H%M%S.%f'), datetime.datetime)
    # success observation is for success getting volume config from api
    # initialized is from initializer
    assert [','.join(o['labels']) for o in initializer_metrics.observations] == [',success', ',initialized']


def test_force_update_valid_domain(domains_config, initializer_metrics):
    worker_id, hostname = 'worker1', 'force-update.domain'
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    worker_ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    # set forced update for the worker
    domains_config.keys.worker_force_update.set(worker_id, '')
    # set valid mock volume config in api
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = {'id': worker_id, 'hostname': hostname, 'zone': config.CWM_ZONE}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, worker_ready_for_deployment_key]) == {
        worker_ready_for_deployment_key: '',
        volume_config_key: ''
   }
    assert_volume_config(domains_config, worker_id, {
        'zone': config.CWM_ZONE
    }, '')
    # success observation is for success getting volume config from api
    # initialized is from initializer
    assert [','.join(o['labels']) for o in initializer_metrics.observations] == [',success', ',initialized']


def test_force_update_invalid_domain(domains_config, initializer_metrics):
    worker_id, hostname = 'worker1', 'force-update-invalid.domain'
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    force_delete_domain_key = domains_config.keys.worker_force_delete._(worker_id)
    worker_ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    # set forced update for the worker
    domains_config.keys.worker_force_update.set(worker_id, '')
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, worker_ready_for_deployment_key]) == {
        force_delete_domain_key: '',
        volume_config_key: ''
    }
    volume_config = json.loads(domains_config.keys.volume_config.get(worker_id))
    assert set(volume_config.keys()) == {'__error', '__last_update'}
    assert volume_config['__error'] == 'mismatched worker_id'
    assert isinstance(common.strptime(volume_config['__last_update'], '%Y%m%dT%H%M%S'), datetime.datetime)
    # error observation is for error getting volume config from api
    # invalid_volume_zone is from initializer
    assert [','.join(o['labels']) for o in initializer_metrics.observations] == [',error', ',invalid_volume_zone']


def test_force_delete_domain_not_allowed_cancel(domains_config, initializer_metrics):
    worker_id, hostname = 'worker1', 'force-delete.domain'
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_initialize_key = domains_config.keys.hostname_initialize._(hostname)
    force_delete_domain_key = domains_config.keys.worker_force_delete._(worker_id)
    domains_config.keys.worker_force_delete.set(worker_id, '')
    domains_config.keys.hostname_initialize.set(hostname, '')
    domains_config._cwm_api_volume_configs['hostname:{}'.format(hostname)] = {'id': worker_id, 'hostname': hostname, 'zone': config.CWM_ZONE}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key]) == {
        hostname_initialize_key: '',
        force_delete_domain_key: '',
        volume_config_key: ''
   }
    assert_volume_config(domains_config, worker_id, {
        'zone': config.CWM_ZONE
    }, '')
    # success observation is for success getting volume config from api
    assert [','.join(o['labels']) for o in initializer_metrics.observations] == [',success']
