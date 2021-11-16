from cwm_worker_operator import nas_checker, common


def test_single_iteration(domains_config, deployments_manager):
    deployments_manager.cluster_nodes = [
        {'name': 'not_worker', 'is_worker': False},
        {'name': 'minikube', 'is_worker': True},
    ]
    deployments_manager.check_node_nas_responses['minikube'] = {
        '1.2.3.4': False,
        '5.6.7.8': True
    }
    nas_checker.run_single_iteration(domains_config, deployments_manager)
    assert not domains_config.keys.node_nas_is_healthy.get('minikube:1.2.3.4')
    assert domains_config.keys.node_nas_is_healthy.get('minikube:5.6.7.8')
    assert (common.now() - domains_config.keys.node_nas_last_check.get('minikube:1.2.3.4')).total_seconds() < 10
    assert (common.now() - domains_config.keys.node_nas_last_check.get('minikube:5.6.7.8')).total_seconds() < 10
