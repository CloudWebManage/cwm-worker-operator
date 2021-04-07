from cwm_worker_operator import cleaner


def test_cleaner(domains_config, deployments_manager):
    # no valid node in cluster - no action performed
    cleaner.run_single_iteration(domains_config, deployments_manager)
    assert deployments_manager.calls == []

    # got a valid node in cluster - cleanup pod created - no cache directories in node - no cleanup performed
    deployments_manager.cluster_nodes = [
        {'name': 'invalid-node-1', 'is_worker': False, 'unschedulable': False},
        {'name': 'invalid-node-2', 'is_worker': False, 'unschedulable': True},
        {'name': 'invalid-node-3', 'is_worker': True, 'unschedulable': True},
        {'name': 'valid-node-4', 'is_worker': True, 'unschedulable': False},
    ]
    cleaner.run_single_iteration(domains_config, deployments_manager)
    assert len(deployments_manager.calls) == 1
    assert deployments_manager.calls[0][0] == 'node_cleanup_pod'
    ncp = deployments_manager.calls[0][1][0]
    assert ncp.mock_calls == [
        ('delete', [True]),
        ('cordon', []),
        ('kubectl_create', [{
            'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'cwm-worker-operator-node-cleanup', 'namespace': 'default'},
            'spec': {
                'nodeSelector': {'kubernetes.io/hostname': 'valid-node-4'},
                'tolerations': [
                    {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"},
                    {"key": "node.kubernetes.io/unschedulable", "operator": "Exists", "effect": "NoSchedule"},
                ],
                'containers': [{
                    'name': 'nodecleanup', 'image': 'alpine',
                    'command': ['sh', '-c', 'while true; do sleep 86400; done'],
                    'volumeMounts': [{'name': 'cache', 'mountPath': '/cache'}]
                }],
                'volumes': [{'name': 'cache', 'hostPath': {'path': '/remote/cache', 'type': 'DirectoryOrCreate'}}]
            }
        }]),
        ('kubectl_get_pod', []),
        ('list_cache_namespaces', []),
        ('uncordon', []),
        ('delete', [False])
    ]

    # got a node in cluster - cleanup pod created - got a cache directory - worker is available and has pods on node - no action performed
    deployments_manager.mock_worker_has_pod_on_node = True
    with domains_config.get_ingress_redis() as r:
        r.set('worker:available:example007.com', "")
    deployments_manager.calls = []
    deployments_manager.node_cleanup_pod_mock_cache_namespaces = ['example007--com']
    cleaner.run_single_iteration(domains_config, deployments_manager)
    assert len(deployments_manager.calls) == 2
    assert deployments_manager.calls[1] == ('worker_has_pod_on_node', ['example007--com', 'valid-node-4'])
    assert deployments_manager.calls[0][0] == 'node_cleanup_pod'
    ncp = deployments_manager.calls[0][1][0]
    assert ncp.mock_calls == [
        ('delete', [True]),
        ('cordon', []),
        ('kubectl_create', [{
            'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'name': 'cwm-worker-operator-node-cleanup', 'namespace': 'default'},
            'spec': {
                'nodeSelector': {'kubernetes.io/hostname': 'valid-node-4'},
                'tolerations': [
                    {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"},
                    {"key": "node.kubernetes.io/unschedulable", "operator": "Exists", "effect": "NoSchedule"},
                ],
                'containers': [{
                    'name': 'nodecleanup', 'image': 'alpine',
                    'command': ['sh', '-c', 'while true; do sleep 86400; done'],
                    'volumeMounts': [{'name': 'cache', 'mountPath': '/cache'}]
                }],
                'volumes': [{'name': 'cache', 'hostPath': {'path': '/remote/cache', 'type': 'DirectoryOrCreate'}}]
            }
        }]),
        ('kubectl_get_pod', []),
        ('list_cache_namespaces', []),
        ('uncordon', []),
        ('delete', [False])
    ]

    # got a node in cluster - cleanup pod created - got a cache directory - worker is not available - cleanup performed
    with domains_config.get_ingress_redis() as r:
        r.delete('worker:available:example007.com')
    deployments_manager.calls = []
    deployments_manager.node_cleanup_pod_mock_cache_namespaces = ['example007--com']
    cleaner.run_single_iteration(domains_config, deployments_manager)
    assert len(deployments_manager.calls) == 1
    assert deployments_manager.calls[0][0] == 'node_cleanup_pod'
    ncp = deployments_manager.calls[0][1][0]
    assert ncp.mock_calls == [
        ('delete', [True]),
        ('cordon', []),
        ('kubectl_create', [{
            'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'name': 'cwm-worker-operator-node-cleanup', 'namespace': 'default'},
            'spec': {
                'nodeSelector': {'kubernetes.io/hostname': 'valid-node-4'},
                'tolerations': [
                    {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"},
                    {"key": "node.kubernetes.io/unschedulable", "operator": "Exists", "effect": "NoSchedule"},
                ],
                'containers': [{
                    'name': 'nodecleanup', 'image': 'alpine',
                    'command': ['sh', '-c', 'while true; do sleep 86400; done'],
                    'volumeMounts': [{'name': 'cache', 'mountPath': '/cache'}]
                }],
                'volumes': [{'name': 'cache', 'hostPath': {'path': '/remote/cache', 'type': 'DirectoryOrCreate'}}]
            }
        }]),
        ('kubectl_get_pod', []),
        ('list_cache_namespaces', []),
        ('clear_cache_namespace', ['example007--com']),
        ('uncordon', []),
        ('delete', [False])
    ]

    # got a node in cluster - cleanup pod created - got a cache directory - worker is available but doesn't have pods - cleanup performed
    deployments_manager.mock_worker_has_pod_on_node = False
    with domains_config.get_ingress_redis() as r:
        r.set('worker:available:example007.com', "")
    deployments_manager.calls = []
    deployments_manager.node_cleanup_pod_mock_cache_namespaces = ['example007--com']
    cleaner.run_single_iteration(domains_config, deployments_manager)
    assert len(deployments_manager.calls) == 2
    assert deployments_manager.calls[1] == ('worker_has_pod_on_node', ['example007--com', 'valid-node-4'])
    assert deployments_manager.calls[0][0] == 'node_cleanup_pod'
    ncp = deployments_manager.calls[0][1][0]
    assert ncp.mock_calls == [
        ('delete', [True]),
        ('cordon', []),
        ('kubectl_create', [{
            'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'name': 'cwm-worker-operator-node-cleanup', 'namespace': 'default'},
            'spec': {
                'nodeSelector': {'kubernetes.io/hostname': 'valid-node-4'},
                'tolerations': [
                    {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"},
                    {"key": "node.kubernetes.io/unschedulable", "operator": "Exists", "effect": "NoSchedule"},
                ],
                'containers': [{
                    'name': 'nodecleanup', 'image': 'alpine',
                    'command': ['sh', '-c', 'while true; do sleep 86400; done'],
                    'volumeMounts': [{'name': 'cache', 'mountPath': '/cache'}]
                }],
                'volumes': [{'name': 'cache', 'hostPath': {'path': '/remote/cache', 'type': 'DirectoryOrCreate'}}]
            }
        }]),
        ('kubectl_get_pod', []),
        ('list_cache_namespaces', []),
        ('clear_cache_namespace', ['example007--com']),
        ('uncordon', []),
        ('delete', [False])
    ]
