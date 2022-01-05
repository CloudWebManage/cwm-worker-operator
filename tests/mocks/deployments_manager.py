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
        self.dns_healthchecks = []
        self.dns_records = []
        self.dns_healthcheck_counter = 0
        self.minio_nginx_pods_on_node = []
        self.check_nodes_nas_response = {}
        self.deploy_preprocess_specs_results = {}

    def init(self, deployment_config):
        self.calls.append(('init', [deployment_config]))

    def deploy_external_service(self, deployment_config):
        self.calls.append(('deploy_external_service', [deployment_config]))

    def deploy_extra_objects(self, deployment_config, extra_objects):
        self.calls.append(('deploy_extra_objects', [deployment_config, extra_objects]))

    def deploy_preprocess_specs(self, specs):
        self.calls.append(('deploy_preprocess_specs', [specs]))
        return {k: self.deploy_preprocess_specs_results.get(k, 'preprocess_result') for k in specs.keys()}

    def deploy(self, deployment_config, **kwargs):
        self.calls.append(('deploy', [deployment_config, kwargs]))
        if self.deploy_raise_exception:
            raise Exception('Mock Deploy Exception')

    def is_ready(self, namespace_name, deployment_type, minimal_check=False):
        self.calls.append(('is_ready', [namespace_name, deployment_type, minimal_check]))
        return self.namespace_deployment_type_is_ready.get('{}-{}{}'.format(namespace_name, deployment_type, '-minimal' if minimal_check else ''))

    def get_hostname(self, namespace_name, deployment_type):
        self.calls.append(('get_hostname', [namespace_name, deployment_type]))
        return self.namespace_deployment_type_hostname.get('{}-{}'.format(namespace_name, deployment_type))

    def verify_worker_access(self, hostname, log_kwargs, **kwargs):
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

    def iterate_dns_healthchecks(self):
        for dns_healthcheck in self.dns_healthchecks:
            yield dns_healthcheck

    def iterate_dns_records(self):
        for dns_record in self.dns_records:
            yield dns_record

    def set_dns_healthcheck(self, node_name, node_ip):
        self.calls.append(('set_dns_healthcheck', [node_name, node_ip]))
        self.dns_healthcheck_counter += 1
        return 'created-healthcheck-{}'.format(self.dns_healthcheck_counter)

    def set_dns_record(self, node_name, node_ip, healthcheck_id):
        self.calls.append(('set_dns_record', [node_name, node_ip, healthcheck_id]))

    def delete_dns_healthcheck(self, healthcheck_id):
        self.calls.append(('delete_dns_healthcheck', [healthcheck_id]))

    def delete_dns_record(self, record_id):
        self.calls.append(('delete_dns_record', [record_id]))

    def iterate_minio_nginx_pods_on_node(self, node_name):
        for namespace_name, pod_name in self.minio_nginx_pods_on_node:
            yield namespace_name, pod_name

    def pod_exec(self, namespace_name, pod_name, *args):
        self.calls.append(('pod_exec', [namespace_name, pod_name, *args]))

    def check_nodes_nas(self, node_names):
        return self.check_nodes_nas_response
