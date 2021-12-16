import os
import shutil
import datetime
from glob import glob

from cwm_worker_operator import nas_checker, common, config


def test_single_iteration(domains_config, deployments_manager):
    minikube_status_path = os.path.join(config.LOCAL_STORAGE_PATH, 'nas_checker', 'status_details', 'minikube')
    shutil.rmtree(minikube_status_path, ignore_errors=True)
    domains_config.keys.node_nas_is_healthy.set('invalid:0.0.0.0', True)
    domains_config.keys.node_nas_is_healthy.set('minikube:1.1.1.1', True)
    deployments_manager.cluster_nodes = [
        {'name': 'not_worker', 'is_worker': False},
        {'name': 'minikube', 'is_worker': True},
    ]
    deployments_manager.check_node_nas_responses['minikube'] = {
        '1.2.3.4': {'is_healthy': False, 'foo': 'bar'},
        '5.6.7.8': {'is_healthy': True, 'baz': 'bax'}
    }
    now = common.now()
    nas_checker.run_single_iteration(domains_config, deployments_manager, now=now)
    assert not domains_config.keys.node_nas_is_healthy.get('minikube:1.2.3.4')
    assert domains_config.keys.node_nas_is_healthy.get('minikube:5.6.7.8')
    assert (common.now() - domains_config.keys.node_nas_last_check.get('minikube:1.2.3.4')).total_seconds() < 10
    assert (common.now() - domains_config.keys.node_nas_last_check.get('minikube:5.6.7.8')).total_seconds() < 10
    assert not domains_config.keys.node_nas_is_healthy.exists('invalid:0.0.0.0')
    assert not domains_config.keys.node_nas_is_healthy.exists('minikube:1.1.1.1')
    assert glob('{}/**'.format(minikube_status_path), recursive=True) == [
        os.path.join(minikube_status_path, ''),
        os.path.join(minikube_status_path, '1.2.3.4.json'),
        os.path.join(minikube_status_path, '1.2.3.4-last-errors'),
        os.path.join(minikube_status_path, '1.2.3.4-last-errors', '{}.json'.format(now.strftime('%Y-%m-%dT%H-%M-%S'))),
        os.path.join(minikube_status_path, '5.6.7.8.json'),
    ]
    nas_checker.run_single_iteration(domains_config, deployments_manager,
                                     now=now + datetime.timedelta(minutes=1))
    nas_checker.run_single_iteration(domains_config, deployments_manager,
                                     now=now + datetime.timedelta(minutes=2),
                                     max_last_errors=2)
    assert glob(os.path.join(minikube_status_path, '1.2.3.4-last-errors', '*')) == [
        os.path.join(minikube_status_path, '1.2.3.4-last-errors', '{}.json'.format((now + datetime.timedelta(minutes=2)).strftime('%Y-%m-%dT%H-%M-%S'))),
        os.path.join(minikube_status_path, '1.2.3.4-last-errors', '{}.json'.format((now + datetime.timedelta(minutes=1)).strftime('%Y-%m-%dT%H-%M-%S'))),
    ]
