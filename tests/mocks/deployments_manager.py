from contextlib import contextmanager

from cwm_worker_operator.deployments_manager import DeploymentsManager, NodeCleanupPod


class MockNodeCleanupPod(NodeCleanupPod):

    def __init__(self, namespace_name, pod_name, node_name):
        super(MockNodeCleanupPod, self).__init__(namespace_name, pod_name, node_name)
        self.mock_calls = []
        self.mock_get_pod = {
            'status': {
                'conditions': [
                    {'type': 'Ready', 'status': 'True'}
                ]
            }
        }
        self.mock_cache_namespaces = []

    def kubectl_create(self, pod):
        self.mock_calls.append(('kubectl_create', [pod]))

    def kubectl_get_pod(self):
        self.mock_calls.append(('kubectl_get_pod', []))
        return self.mock_get_pod

    def cordon(self):
        self.mock_calls.append(('cordon', []))

    def uncordon(self):
        self.mock_calls.append(('uncordon', []))

    def delete(self, wait):
        self.mock_calls.append(('delete', [wait]))

    def list_cache_namespaces(self):
        self.mock_calls.append(('list_cache_namespaces', []))
        return self.mock_cache_namespaces

    def clear_cache_namespace(self, cache_namespace_name):
        self.mock_calls.append(('clear_cache_namespace', [cache_namespace_name]))


class MockDeploymentsManager(DeploymentsManager):

    def __init__(self):
        self.calls = []
        self.deploy_raise_exception = False
        self.namespace_deployment_type_is_ready = {}
        self.namespace_deployment_type_hostname = {}
        self.hostname_verify_worker_access = {}
        self.all_releases = []
        self.prometheus_metrics = {}
        self.cluster_nodes = []
        self.node_cleanup_pod_class = MockNodeCleanupPod
        self.node_cleanup_pod_mock_cache_namespaces = []
        self.mock_worker_has_pod_on_node = True
        self.kube_metrics = {}

    def init(self, deployment_config):
        self.calls.append(('init', [deployment_config]))

    def deploy_external_service(self, deployment_config):
        self.calls.append(('deploy_external_service', [deployment_config]))

    def deploy_extra_objects(self, deployment_config, extra_objects):
        self.calls.append(('deploy_extra_objects', [deployment_config, extra_objects]))

    def deploy(self, deployment_config, **kwargs):
        self.calls.append(('deploy', [deployment_config, kwargs]))
        if self.deploy_raise_exception:
            raise Exception('Mock Deploy Exception')

    def is_ready(self, namespace_name, deployment_type):
        self.calls.append(('is_ready', [namespace_name, deployment_type]))
        return self.namespace_deployment_type_is_ready.get('{}-{}'.format(namespace_name, deployment_type))

    def get_hostname(self, namespace_name, deployment_type):
        self.calls.append(('get_hostname', [namespace_name, deployment_type]))
        return self.namespace_deployment_type_hostname.get('{}-{}'.format(namespace_name, deployment_type))

    def verify_worker_access(self, hostname, log_kwargs):
        self.calls.append(('verify_worker_access', [hostname, log_kwargs]))
        return self.hostname_verify_worker_access.get(hostname, False)

    def delete(self, namespace_name, deployment_type, **kwargs):
        self.calls.append(('delete', [namespace_name, deployment_type, kwargs]))

    def iterate_all_releases(self):
        for release in self.all_releases:
            yield release

    def get_prometheus_metrics(self, namespace_name):
        return self.prometheus_metrics[namespace_name]

    def get_kube_metrics(self, namespace_name):
        return self.kube_metrics[namespace_name]

    def iterate_cluster_nodes(self):
        for node in self.cluster_nodes:
            yield node

    @contextmanager
    def node_cleanup_pod(self, node_name):
        with super(MockDeploymentsManager, self).node_cleanup_pod(node_name) as ncp:
            self.calls.append(('node_cleanup_pod', [ncp]))
            ncp.mock_cache_namespaces = self.node_cleanup_pod_mock_cache_namespaces
            yield ncp

    def worker_has_pod_on_node(self, namespace_name, node_name):
        self.calls.append(('worker_has_pod_on_node', [namespace_name, node_name]))
        return self.mock_worker_has_pod_on_node
