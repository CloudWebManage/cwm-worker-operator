import os
import json
import shutil
from glob import glob

from cwm_worker_operator import workers_checker, common, config


def test(domains_config, deployments_manager):
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker'), ignore_errors=True)
    worker_id = 'worker1'
    namespace_name = common.get_namespace_name_from_worker_id(worker_id)
    # workers_checker will get health for this helm release namesapce
    deployments_manager.all_releases = [
        {
            "namespace": namespace_name,
        }
    ]
    # mock get_health response, doesn't matter what's the content, it just saves it as-is
    deployments_manager.namespace_deployment_type_get_health['{}-minio'.format(namespace_name)] = {
        'foo': 'bar'
    }
    # workers_checker checks that worker_id is valid, this mocks a valid response from cwm api for this worker_id
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = {'instanceId': worker_id}
    workers_checker.run_single_iteration(domains_config, deployments_manager)
    assert deployments_manager.calls == [('get_all_namespaces', []),
                                         ('get_health', [namespace_name, 'minio'])]
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id)
    ]) == {
        domains_config.keys.worker_health._(worker_id): '{"foo": "bar"}',
        domains_config.keys.volume_config._(worker_id): ''
    }
    # mock an empty get_health response, this should delete the corresponding health key from redis
    del deployments_manager.namespace_deployment_type_get_health['{}-minio'.format(namespace_name)]
    workers_checker.run_single_iteration(domains_config, deployments_manager)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id)
    ]) == {
       domains_config.keys.volume_config._(worker_id): ''
    }
    # set a worker_health key for worker2 - this will cause workers_checker to check it (content doesn't matter)
    domains_config.keys.worker_health.set('worker2', 'health..')
    domains_config._cwm_api_volume_configs['id:worker2'] = {'instanceId': 'worker2'}
    deployments_manager.namespace_deployment_type_get_health['cwm-worker-worker2-minio'] = {
        'worker': 2
    }
    # set some namespaces to be checked by worker_checker, only valid worker_ids will be checked
    deployments_manager.all_namespaces += [
        'default', 'cwm-worker-worker3', 'kube-system', 'cwm-worker-123456'
    ]
    domains_config._cwm_api_volume_configs['id:worker3'] = {'instanceId': 'worker3'}
    deployments_manager.namespace_deployment_type_get_health['cwm-worker-worker3-minio'] = {
        'worker': 3
    }
    workers_checker.run_single_iteration(domains_config, deployments_manager)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id),
        domains_config.keys.volume_config._('worker2'),
        domains_config.keys.volume_config._('worker3'),
        domains_config.keys.volume_config._('123456'),
    ]) == {
        domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.volume_config._('worker2'): '',
        domains_config.keys.volume_config._('worker3'): '',
        domains_config.keys.volume_config._('123456'): '',
        domains_config.keys.worker_health._('worker2'): '{"worker": 2}',
        domains_config.keys.worker_health._('worker3'): '{"worker": 3}',
    }
    paths = sorted([
        path.replace('/workers_checker/health/', '') for path in [
            path.replace(config.LOCAL_STORAGE_PATH, '') for path in glob('{}/**'.format(config.LOCAL_STORAGE_PATH), recursive=True)
        ]
        if path.startswith('/workers_checker/health/')
    ])
    assert len(paths) == 6
    assert paths[0] == 'worker1'
    assert paths[1].startswith('worker1/')
    with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[1])) as f:
        assert json.load(f) == {'foo': 'bar'}
    assert paths[2] == 'worker2'
    assert paths[3].startswith('worker2/')
    with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[3])) as f:
        assert json.load(f) == {'worker': 2}
    assert paths[4] == 'worker3'
    assert paths[5].startswith('worker3/')
    with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[5])) as f:
        assert json.load(f) == {'worker': 3}
