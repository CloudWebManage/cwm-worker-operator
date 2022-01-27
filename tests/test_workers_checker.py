import datetime
import os
import json
import shutil
import random
from glob import glob

import prometheus_client
import prometheus_client.samples

from cwm_worker_operator import workers_checker, common, config


def test(domains_config, deployments_manager):
    metrics_registry = prometheus_client.CollectorRegistry()
    metrics = workers_checker.WorkersCheckerMetrics(registry=metrics_registry)
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
    config.WORKERS_CHECKER_ALERT_POD_MISSING_SECONDS = 1
    first_now = now = common.now()
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert deployments_manager.calls == [('get_all_namespaces', []), ('get_health', [namespace_name, 'minio']),
                                         ('get_all_namespaces', []), ('get_health', [namespace_name, 'minio']),
                                         ('get_all_namespaces', []), ('get_health', [namespace_name, 'minio'])]
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id)
    ]) == {
        domains_config.keys.worker_health._(worker_id): '{"foo": "bar"}',
        domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.alerts._(): ' | '.join([
            '{"type": "cwm-worker-operator-logs", "msg": "workers_checker (worker1): pod is missing for 1 seconds", "kwargs": {}}',
            '{"type": "cwm-worker-operator-logs", "msg": "workers_checker (worker1): pod is missing for 2 seconds", "kwargs": {}}',
        ])
    }
    # mock an empty get_health response, this should delete the corresponding health key from redis
    del deployments_manager.namespace_deployment_type_get_health['{}-minio'.format(namespace_name)]
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id),
        domains_config.keys.alerts._()
    ]) == {
       domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.alerts._(): ''
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
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id),
        domains_config.keys.volume_config._('worker2'),
        domains_config.keys.volume_config._('worker3'),
        domains_config.keys.volume_config._('123456'),
        domains_config.keys.alerts._(),
    ]) == {
        domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.volume_config._('worker2'): '',
        domains_config.keys.volume_config._('worker3'): '',
        domains_config.keys.volume_config._('123456'): '',
        domains_config.keys.worker_health._('worker2'): '{"worker": 2}',
        domains_config.keys.worker_health._('worker3'): '{"worker": 3}',
        domains_config.keys.alerts._(): '',
    }
    paths = sorted([
        path.replace('/workers_checker/health/', '') for path in [
            path.replace(config.LOCAL_STORAGE_PATH, '') for path in glob('{}/**'.format(config.LOCAL_STORAGE_PATH), recursive=True)
        ]
        if path.startswith('/workers_checker/health/')
    ])
    assert len(paths) == 9
    assert paths[0] == 'worker1'
    assert paths[1].startswith('worker1/')
    with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[1])) as f:
        assert json.load(f) == {'foo': 'bar'}
    assert paths[2].startswith('worker1/')
    assert paths[3].startswith('worker1/')
    assert paths[4].startswith('worker1/')
    assert paths[5] == 'worker2'
    assert paths[6].startswith('worker2/')
    with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[6])) as f:
        assert json.load(f) == {'worker': 2}
    assert paths[7] == 'worker3'
    assert paths[8].startswith('worker3/')
    with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[8])) as f:
        assert json.load(f) == {'worker': 3}
    all_worker_conditions = list(common.local_storage_json_last_items_iterator('workers_checker/conditions/worker1'))
    assert len(all_worker_conditions) == 4
    assert all_worker_conditions[0] == {
        'datetime': common.strptime((first_now + datetime.timedelta(seconds=3)).strftime('%Y-%m-%dT%H-%M-%S'), '%Y-%m-%dT%H-%M-%S'),
        'item': {
            'has_missing_pods_seconds': 2.0,
            'has_unknown_pods': False,
            'namespace_terminating_seconds': None,
            'pod_error_crash_loop': False,
            'pod_pending_seconds': None
        }
    }
    worker_state_metrics = {}
    for metric in metrics_registry.collect():
        sample: prometheus_client.samples.Sample
        for sample in metric.samples:
            if sample.name == 'workers_checker_states_total':
                worker_state_metrics.setdefault(sample.labels['worker_id'], {}).setdefault(sample.labels['state'], 0)
                worker_state_metrics[sample.labels['worker_id']][sample.labels['state']] += sample.value
    assert worker_state_metrics == {
        'worker1': {
            'has_missing_pods': 3.0
        }
    }




def get_mock_deployment_deployment(name, conditions=None, replicas=None, **kwargs):
    return {
        'name': name,
        'conditions': {
            'Available': 'True:MinimumReplicasAvailable',
            'Progressing': 'True:NewReplicaSetAvailable',
            **(conditions if conditions else {})
        },
        'replicas': {
            'available': 1,
            'ready': 1,
            'replicas': 1,
            'updated': 1,
            **(replicas if replicas else {})
        },
        **kwargs
    }


def get_mock_pod(name, conditions=None, containerStatuses=None,
                 first_container_name=None, first_container_statuses=None,
                 **kwargs):
    return {
        'name': name,
        'nodeName': 'worker{}'.format(random.randrange(1, 10)),
        'phase': 'Running',
        'conditions': {
            'ContainersReady': 'True',
            'Initialized': 'True',
            'PodScheduled': 'True',
            'Ready': 'True',
            **(conditions if conditions else {})
        },
        'containerStatuses': {
            (first_container_name if first_container_name else 'app'): {
                'ready': True,
                'restartCount': 0,
                'started': True,
                'state': {
                    'state': 'running'
                },
                **(first_container_statuses if first_container_statuses else {})
            },
            **(containerStatuses if containerStatuses else {})
        },
        **kwargs
    }


def get_mock_deployment(name, num_pods=1, deployment_kwargs=None, pod_kwargs=None):
    return {
        'deployments': [
            get_mock_deployment_deployment(name, **(deployment_kwargs if deployment_kwargs else {}))
        ],
        'pods': [
            get_mock_pod('{}-lko239df'.format(name), **(pod_kwargs if pod_kwargs else {}))
            for _ in range(num_pods)
        ]
    }


def get_mock_health(
        is_ready=True, namespace_name='cwm-worker-uwhdfn32d', namespace_phase='Active',
        external_scaler_kwargs=None, logger_kwargs=None, nginx_kwargs=None, server_kwargs=None,
        unknown_kwargs=None
):
    return {
        'is_ready': is_ready,
        'namespace': {
            'name': namespace_name,
            'phase': namespace_phase
        },
        'deployments': {
            'external-scaler': get_mock_deployment('minio-external-scaler', **(external_scaler_kwargs if external_scaler_kwargs else {})),
            'logger': get_mock_deployment('minio-logger', **(logger_kwargs if logger_kwargs else {})),
            'nginx': get_mock_deployment('minio-nginx', **(nginx_kwargs if nginx_kwargs else {})),
            'server': get_mock_deployment('minio-server', **{'num_pods': 5, **(server_kwargs if server_kwargs else {})}),
            'unknown': {
                'deployments': [],
                'pods': [],
                **(unknown_kwargs if unknown_kwargs else {})
            }
        },
    }


def test_check_worker_conditions_valid():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i, health in enumerate([
        get_mock_health(unknown_kwargs={'pods': [{}]}),
        get_mock_health(server_kwargs={'num_pods': 0}),
        get_mock_health(namespace_phase='Terminating'),
        get_mock_health(server_kwargs={'pod_kwargs': {'first_container_statuses': {'state': {'reason': 'CrashLoopBackOff'}}}}),
        get_mock_health(server_kwargs={'pod_kwargs': {'first_container_statuses': {'state': {'reason': 'Error'}}}}),
        get_mock_health(server_kwargs={'pod_kwargs': {'phase': 'Pending'}}),
        get_mock_health(),
    ]):
        common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
    assert workers_checker.get_worker_conditions(worker_id) == {
        'pod_pending_seconds': None,
        'pod_error_crash_loop': False,
        'namespace_terminating_seconds': None,
        'has_missing_pods_seconds': None,
        'has_unknown_pods': False,
    }


def test_check_worker_conditions_pod_pending():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i, health in enumerate([
        get_mock_health(server_kwargs={'pod_kwargs': {'phase': 'Pending'}}),
        get_mock_health(),
        get_mock_health(server_kwargs={'pod_kwargs': {'phase': 'Pending'}}),
        get_mock_health(server_kwargs={'pod_kwargs': {'phase': 'Pending'}}),
        get_mock_health(server_kwargs={'pod_kwargs': {'phase': 'Pending'}}),
    ]):
        common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
    assert workers_checker.get_worker_conditions(worker_id) == {
        'pod_pending_seconds': 2.0,
        'pod_error_crash_loop': False,
        'namespace_terminating_seconds': None,
        'has_missing_pods_seconds': None,
        'has_unknown_pods': False,
    }


def test_check_worker_conditions_pod_error_crash_loop():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    for reason in ['Error', 'CrashLoopBackOff']:
        shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
        now = common.now()
        for i, health in enumerate([
            get_mock_health(),
            get_mock_health(server_kwargs={'pod_kwargs': {'first_container_statuses': {'state': {'reason': reason}}}}),
        ]):
            common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
        assert workers_checker.get_worker_conditions(worker_id) == {
            'pod_pending_seconds': None,
            'pod_error_crash_loop': True,
            'namespace_terminating_seconds': None,
            'has_missing_pods_seconds': None,
            'has_unknown_pods': False,
        }


def test_check_worker_conditions_namespace_terminating():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i, health in enumerate([
        get_mock_health(namespace_phase='Terminating'),
        get_mock_health(),
        get_mock_health(namespace_phase='Terminating'),
        get_mock_health(namespace_phase='Terminating'),
        get_mock_health(namespace_phase='Terminating'),
    ]):
        common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
    assert workers_checker.get_worker_conditions(worker_id) == {
        'pod_pending_seconds': None,
        'pod_error_crash_loop': False,
        'namespace_terminating_seconds': 2.0,
        'has_missing_pods_seconds': None,
        'has_unknown_pods': False
    }


def test_check_worker_conditions_has_missing_pods():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i, health in enumerate([
        get_mock_health(),
        get_mock_health(server_kwargs={'num_pods': 0}),
        get_mock_health(server_kwargs={'num_pods': 0}),
    ]):
        common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
    assert workers_checker.get_worker_conditions(worker_id) == {
        'pod_pending_seconds': None,
        'pod_error_crash_loop': False,
        'namespace_terminating_seconds': None,
        'has_missing_pods_seconds': 1,
        'has_unknown_pods': False
    }


def test_check_worker_conditions_has_unknown_pods():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i, health in enumerate([
        get_mock_health(),
        get_mock_health(),
        get_mock_health(unknown_kwargs={'pods': [{}]}),
    ]):
        common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
    assert workers_checker.get_worker_conditions(worker_id) == {
        'pod_pending_seconds': None,
        'pod_error_crash_loop': False,
        'namespace_terminating_seconds': None,
        'has_missing_pods_seconds': None,
        'has_unknown_pods': True
    }
