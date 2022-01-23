from cwm_worker_operator import deleter, updater, config
from cwm_worker_operator.common import get_namespace_name_from_worker_id

from .common import set_volume_config_key


def test_delete(domains_config, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    deleter.delete(worker_id, domains_config=domains_config, deployments_manager=deployments_manager)
    assert domains_config._get_all_redis_pools_values() == {}
    assert deployments_manager.calls == [
        ('delete', [namespace_name, 'minio', {
            'delete_helm': True, 'delete_namespace': False,
            'timeout_string': None, 'delete_data': False, 'delete_data_config': None,
            'force_now': False
        }])
    ]


def test_deleter_daemon(domains_config, deployments_manager, deleter_metrics):
    domains_config.set_worker_force_delete('worker1', allow_cancel=True)
    set_volume_config_key(domains_config, worker_id='worker1', hostname='www.worker.one')
    domains_config.set_worker_force_delete('worker2', allow_cancel=True)
    set_volume_config_key(domains_config, worker_id='worker2', hostname='www.worker.two')
    deleter.run_single_iteration(domains_config, deleter_metrics, deployments_manager)
    assert [o['labels'][1] for o in deleter_metrics.observations] == ['success', 'success']
    assert set([c[0] + '-' + c[1][0] for c in deployments_manager.calls]) == {
        'delete-{}'.format(get_namespace_name_from_worker_id('worker1')),
        'delete-{}'.format(get_namespace_name_from_worker_id('worker2'))
    }


def test_deleter_cancel_if_worker_deployment(domains_config, deployments_manager, deleter_metrics):
    domains_config.keys.hostname_initialize.set('domain1.com', '')
    domains_config.set_worker_force_delete('worker1', allow_cancel=True)
    set_volume_config_key(domains_config, worker_id='worker1', hostname='domain1.com')
    domains_config.set_worker_force_delete('worker2', allow_cancel=True)
    set_volume_config_key(domains_config, worker_id='worker2', hostname='domain2.com')
    deleter.run_single_iteration(domains_config, deleter_metrics, deployments_manager)
    assert set([o['labels'][1] for o in deleter_metrics.observations]) == {'success', 'delete_canceled'}
    assert [c[0] + '-' + c[1][0] for c in deployments_manager.calls] == [
        'delete-{}'.format(get_namespace_name_from_worker_id('worker2'))
    ]


def test_delete_data(domains_config, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    domains_config.keys.worker_aggregated_metrics.set(worker_id, 'foo')
    domains_config.keys.worker_force_delete_data.set(worker_id, updater.CONFIRM_FORCE_DELETE_DATA)
    config.DELETER_DATA_DELETE_CONFIG = {}
    deleter.delete(worker_id, domains_config=domains_config, deployments_manager=deployments_manager)
    assert domains_config._get_all_redis_pools_values() == {}
    assert deployments_manager.calls == [
        ('delete', [namespace_name, 'minio', {
            'delete_helm': True, 'delete_namespace': False,
            'timeout_string': None, 'delete_data': True, 'delete_data_config': {},
            'force_now': False
        }])
    ]
    deployments_manager.calls = []
    domains_config.keys.worker_force_delete_data.set(worker_id, updater.CONFIRM_FORCE_DELETE_DATA)
    config.DELETER_DATA_DELETE_CONFIG = {
        'namespace': '__NAMESPACE_NAME__'
    }
    deleter.delete(worker_id, domains_config=domains_config, deployments_manager=deployments_manager)
    assert domains_config._get_all_redis_pools_values() == {}
    assert deployments_manager.calls == [
        ('delete', [namespace_name, 'minio', {
            'delete_helm': True, 'delete_namespace': False,
            'timeout_string': None, 'delete_data': True,
            'delete_data_config': {'namespace': namespace_name},
            'force_now': False
        }])
    ]
