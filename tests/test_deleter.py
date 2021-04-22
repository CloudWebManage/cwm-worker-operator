import json

from cwm_worker_operator import deleter


def test_delete(domains_config, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    deleter.delete(worker_id, domains_config=domains_config, deployments_manager=deployments_manager)
    assert domains_config._get_all_redis_pools_values() == {}
    assert deployments_manager.calls == [
        ('delete', [namespace_name, 'minio', {'delete_helm': True, 'delete_namespace': False, 'timeout_string': None}])
    ]


def test_deleter_daemon(domains_config, deployments_manager, deleter_metrics):
    domains_config.set_worker_force_delete('worker1', allow_cancel=True)
    domains_config.keys.volume_config.set('worker1', json.dumps({'id': 'worker1', 'hostname': 'www.worker.one'}))
    domains_config.set_worker_force_delete('worker2', allow_cancel=True)
    domains_config.keys.volume_config.set('worker2', json.dumps({'id': 'worker2', 'hostname': 'www.worker.two'}))
    deleter.run_single_iteration(domains_config, deleter_metrics, deployments_manager)
    assert [o['labels'][1] for o in deleter_metrics.observations] == ['success', 'success']
    assert set([c[0] + '-' + c[1][0] for c in deployments_manager.calls]) == {'delete-worker2', 'delete-worker1'}


def test_deleter_cancel_if_worker_deployment(domains_config, deployments_manager, deleter_metrics):
    domains_config.keys.hostname_initialize.set('domain1.com', '')
    domains_config.set_worker_force_delete('worker1', allow_cancel=True)
    domains_config.keys.volume_config.set('worker1', json.dumps({'id': 'worker1', 'hostname': 'domain1.com'}))
    domains_config.set_worker_force_delete('worker2', allow_cancel=True)
    domains_config.keys.volume_config.set('worker2', json.dumps({'id': 'worker2', 'hostname': 'domain2.com'}))
    deleter.run_single_iteration(domains_config, deleter_metrics, deployments_manager)
    assert set([o['labels'][1] for o in deleter_metrics.observations]) == {'success', 'delete_canceled'}
    assert [c[0] + '-' + c[1][0] for c in deployments_manager.calls] == ['delete-worker2']
