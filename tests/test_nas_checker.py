from cwm_worker_operator import nas_checker, common


def test_single_iteration(domains_config, deployments_manager):
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
    nas_checker.run_single_iteration(domains_config, deployments_manager)
    assert not domains_config.keys.node_nas_is_healthy.get('minikube:1.2.3.4')
    assert domains_config.keys.node_nas_is_healthy.get('minikube:5.6.7.8')
    assert (common.now() - domains_config.keys.node_nas_last_check.get('minikube:1.2.3.4')).total_seconds() < 10
    assert (common.now() - domains_config.keys.node_nas_last_check.get('minikube:5.6.7.8')).total_seconds() < 10
    assert not domains_config.keys.node_nas_is_healthy.exists('invalid:0.0.0.0')
    assert not domains_config.keys.node_nas_is_healthy.exists('minikube:1.1.1.1')
