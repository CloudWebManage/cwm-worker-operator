import os
import json
import shutil
import random
import datetime
from glob import glob
from collections import defaultdict

import prometheus_client
import prometheus_client.samples

from cwm_worker_operator import workers_checker, common, config
from cwm_worker_operator.domains_config import WORKER_ID_VALIDATION_API_FAILURE


def get_worker_metric_samples(metrics_registry):
    worker_metric_samples = {}
    worker_metric_samples_buckets = {}
    for metric in metrics_registry.collect():
        sample: prometheus_client.samples.Sample
        for sample in metric.samples:
            if 'worker_id' in sample.labels and 'state' in sample.labels:
                if 'le' in sample.labels:
                    worker_metric_samples_buckets.setdefault(sample.labels['worker_id'], {}).setdefault(sample.labels['state'], {}).setdefault(sample.labels['le'], 0.0)
                    worker_metric_samples_buckets[sample.labels['worker_id']][sample.labels['state']][sample.labels['le']] += sample.value
                else:
                    worker_metric_samples.setdefault(sample.labels['worker_id'], {}).setdefault(sample.labels['state'], 0.0)
                    worker_metric_samples[sample.labels['worker_id']][sample.labels['state']] += sample.value
    res = {}
    for worker_id, metric_samples in worker_metric_samples.items():
        for state, value in metric_samples.items():
            if state not in worker_metric_samples_buckets.get(worker_id, {}):
                res.setdefault(worker_id, {})[state] = value
    for worker_id, metric_samples in worker_metric_samples_buckets.items():
        for state, buckets in metric_samples.items():
            last_value = None
            for bucket_name, value in buckets.items():
                if last_value != value:
                    res.setdefault(worker_id, {}).setdefault(state, {})[bucket_name] = value
                    last_value = value
    return res


def test(domains_config, deployments_manager):
    metrics_registry = prometheus_client.CollectorRegistry()
    metrics = workers_checker.WorkersCheckerMetrics(registry=metrics_registry)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker'), ignore_errors=True)
    worker_id = 'worker1'
    invalid_worker_id = 'worker2'
    namespace_name = common.get_namespace_name_from_worker_id(worker_id)
    invalid_namespace_name = common.get_namespace_name_from_worker_id(invalid_worker_id)
    # workers_checker will get health for these helm release namesapces
    deployments_manager.all_releases = [
        {
            "namespace": namespace_name,
        },
    ]
    deployments_manager.all_namespaces.append('non-worker-namespace')
    deployments_manager.all_namespaces.append(invalid_namespace_name)
    # mock get_health response, doesn't matter what's the content, it just saves it as-is
    deployments_manager.namespace_deployment_type_get_health['{}-minio'.format(namespace_name)] = {
        'foo': 'bar'
    }
    deployments_manager.namespace_deployment_type_get_health['{}-minio'.format(invalid_namespace_name)] = {
        'foo': 'bar'
    }
    # workers_checker checks that worker_id is valid, this mocks a valid response from cwm api for this worker_id
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = {'instanceId': worker_id}
    # for the invalid worker we mock an invalid response without the id
    domains_config._cwm_api_volume_configs['id:{}'.format(invalid_worker_id)] = {}
    config.WORKERS_CHECKER_ALERT_POD_MISSING_SECONDS = config.WORKERS_CHECKER_ALERT_INVALID_WORKER_SECONDS = 1
    first_now = now = common.now()
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert get_worker_metric_samples(metrics_registry) == {}
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert get_worker_metric_samples(metrics_registry) == {
        'worker1': {'has_missing_pods': {'0.5': 0.0, '1.0': 1.0}},
        'worker2': {'invalid_worker': {'0.5': 0.0, '1.0': 1.0}},
    }
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert get_worker_metric_samples(metrics_registry) == {
        'worker1': {'has_missing_pods': {'0.5': 0.0, '1.0': 1.0, '2.0': 2.0}},
        'worker2': {'invalid_worker': {'0.5': 0.0, '1.0': 1.0, '2.0': 2.0}}
    }
    stats = defaultdict(int)
    for call in deployments_manager.calls:
        if call[0] == 'get_all_namespaces':
            assert call[1] == []
            stats['get_all_namespaces'] += 1
        elif call[0] == 'get_health':
            if call[1] == [namespace_name, 'minio']:
                stats['get_health'] += 1
            elif call[1] == [invalid_namespace_name, 'minio']:
                stats['get_health_invalid'] += 1
            else:
                raise Exception("Invalid call: {}".format(call))
        else:
            raise Exception('Invalid call: {}'.format(call))
    assert dict(stats) == {'get_all_namespaces': 3, 'get_health': 3, 'get_health_invalid': 3}
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id),
        domains_config.keys.volume_config._(invalid_worker_id),
        domains_config.keys.alerts._()
    ]) == {
        domains_config.keys.worker_health._(worker_id): '{"foo": "bar", "worker_id_validation": true}',
        domains_config.keys.worker_health._(invalid_worker_id): '{"foo": "bar", "worker_id_validation": "WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID"}',
        domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.volume_config._(invalid_worker_id): '',
        domains_config.keys.alerts._(): ''
    }
    alerts = []
    while True:
        alert = domains_config.alerts_pop()
        if alert:
            alerts.append(alert)
        else:
            break
    expected_alerts = [
        {'kwargs': {}, 'msg': 'workers_checker (worker1): pod is missing for 1 seconds', 'type': 'cwm-worker-operator-logs'},
        {'kwargs': {}, 'msg': 'workers_checker (worker1): pod is missing for 2 seconds', 'type': 'cwm-worker-operator-logs'},
        {'kwargs': {}, 'msg': 'workers_checker (worker2): invalid worker for 1 seconds', 'type': 'cwm-worker-operator-logs'},
        {'kwargs': {}, 'msg': 'workers_checker (worker2): invalid worker for 2 seconds', 'type': 'cwm-worker-operator-logs'},
    ]
    for expected_alert in expected_alerts:
        assert expected_alert in alerts, 'missing alert: {}'.format(expected_alert)
    assert len(alerts) == len(expected_alerts), 'alerts length mismatch: {}'.format(alerts)
    # mock an empty get_health response, this should delete the corresponding health key from redis
    del deployments_manager.namespace_deployment_type_get_health['{}-minio'.format(namespace_name)]
    now += datetime.timedelta(seconds=1)
    workers_checker.run_single_iteration(domains_config, deployments_manager, now=now, metrics=metrics)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(worker_id),
        domains_config.keys.volume_config._(invalid_worker_id),
        domains_config.keys.alerts._()
    ]) == {
        domains_config.keys.volume_config._(worker_id): '',
        domains_config.keys.volume_config._(invalid_worker_id): '',
        domains_config.keys.alerts._(): '',
        domains_config.keys.worker_health._(invalid_worker_id): '{"foo": "bar", "worker_id_validation": "WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID"}'
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
        domains_config.keys.worker_health._('worker2'): '{"worker": 2, "worker_id_validation": true}',
        domains_config.keys.worker_health._('worker3'): '{"worker": 3, "worker_id_validation": true}',
        domains_config.keys.alerts._(): '',
    }
    paths = sorted([
        path.replace('/workers_checker/health/', '') for path in [
            path.replace(config.LOCAL_STORAGE_PATH, '') for path in glob('{}/**'.format(config.LOCAL_STORAGE_PATH), recursive=True)
        ]
        if path.startswith('/workers_checker/health/')
    ])
    expected_paths = [
        {'folder': 'worker1'},
        {'path_starts_with': 'worker1/', 'content': {'foo': 'bar', "worker_id_validation": True}},
        {'path_starts_with': 'worker1/', 'content': {'foo': 'bar', "worker_id_validation": True}},
        {'path_starts_with': 'worker1/', 'content': {'foo': 'bar', "worker_id_validation": True}},
        {'path_starts_with': 'worker1/', 'content': {'__deleted': True, "worker_id_validation": True}},
        {'folder': 'worker2'},
        {'path_starts_with': 'worker2/', 'content': {'foo': 'bar', "worker_id_validation": 'WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID'}},
        {'path_starts_with': 'worker2/', 'content': {'foo': 'bar', "worker_id_validation": 'WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID'}},
        {'path_starts_with': 'worker2/', 'content': {'foo': 'bar', "worker_id_validation": 'WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID'}},
        {'path_starts_with': 'worker2/', 'content': {'foo': 'bar', "worker_id_validation": 'WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID'}},
        {'path_starts_with': 'worker2/', 'content': {'worker': 2, "worker_id_validation": True}},
        {'folder': 'worker3'},
        {'path_starts_with': 'worker3/', 'content': {'worker': 3, "worker_id_validation": True}},
    ]
    assert len(paths) == len(expected_paths)
    for i, expected_path in enumerate(expected_paths):
        if 'folder' in expected_path:
            assert paths[i] == expected_path['folder']
        if 'path_starts_with' in expected_path:
            assert paths[i].startswith(expected_path['path_starts_with'])
        if 'content' in expected_path:
            with open(os.path.join(config.LOCAL_STORAGE_PATH, 'workers_checker', 'health', paths[i])) as f:
                actual_content = json.load(f)
                assert actual_content == expected_path['content'], f'i={i} actual_content={actual_content}'
    all_worker_conditions = list(common.local_storage_json_last_items_iterator('workers_checker/conditions/worker1'))
    assert len(all_worker_conditions) == 4
    assert all_worker_conditions[0] == {
        'datetime': common.strptime((first_now + datetime.timedelta(seconds=3)).strftime('%Y-%m-%dT%H-%M-%S'), '%Y-%m-%dT%H-%M-%S'),
        'item': {
            'has_missing_pods_seconds': 2.0,
            'has_unknown_pods': False,
            'namespace_terminating_seconds': None,
            'pod_error_crash_loop': False,
            'pod_pending_seconds': None,
            'invalid_worker_seconds': None,
        }
    }
    assert get_worker_metric_samples(metrics_registry) == {
        'worker1': {'has_missing_pods': {'0.5': 0.0, '1.0': 1.0, '2.0': 3.0}},
        'worker2': {
            'invalid_worker': {'0.5': 0.0, '1.0': 1.0, '2.0': 2.0, '4.0': 3.0},
            'has_missing_pods': {'0.5': 0.0, '4.0': 1.0}
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
        unknown_kwargs=None, worker_id_validation=True
):
    return {
        'is_ready': is_ready,
        'worker_id_validation': worker_id_validation,
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
        'invalid_worker_seconds': None,
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
        'invalid_worker_seconds': None,
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
            'invalid_worker_seconds': None,
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
        'has_unknown_pods': False,
        'invalid_worker_seconds': None,
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
        'has_unknown_pods': False,
        'invalid_worker_seconds': None,
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
        'has_unknown_pods': True,
        'invalid_worker_seconds': None,
    }


def test_check_worker_conditions_invalid_worker():
    worker_id = 'cwm-worker-test123'
    key = 'workers_checker/health/{}'.format(worker_id)
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i, health in enumerate([
        get_mock_health(),
        get_mock_health(worker_id_validation=WORKER_ID_VALIDATION_API_FAILURE),
        get_mock_health(worker_id_validation=WORKER_ID_VALIDATION_API_FAILURE),
    ]):
        common.local_storage_json_last_items_append(key, health, now_=(now + datetime.timedelta(seconds=i)))
    assert workers_checker.get_worker_conditions(worker_id) == {
        'pod_pending_seconds': None,
        'pod_error_crash_loop': None,
        'namespace_terminating_seconds': None,
        'has_missing_pods_seconds': None,
        'has_unknown_pods': None,
        'invalid_worker_seconds': 1.0,
    }
