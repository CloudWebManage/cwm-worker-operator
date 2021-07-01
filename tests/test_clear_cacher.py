from cwm_worker_operator import common
from cwm_worker_operator.clear_cacher import run_single_iteration


def test_clear_cacher(domains_config, deployments_manager):
    deployments_manager.cluster_nodes = [{
        'name': 'node1',
        'is_worker': True
    }]
    deployments_manager.minio_nginx_pods_on_node = [('namespace1', 'pod1')]
    domains_config._set_mock_volume_config('namespace1', additional_volume_config={
        'clear-cache': '2021-06-05 11:44:33'
    })
    run_single_iteration(domains_config, deployments_manager)
    assert (common.now() - domains_config.get_worker_last_clear_cache('namespace1')).total_seconds() < 5
    assert deployments_manager.calls == [('pod_exec', ['namespace1', 'pod1', 'bash', '-c', 'rm -rf /var/cache/nginx/minio/cache/*'])]
