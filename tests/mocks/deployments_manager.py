from cwm_worker_operator.deployments_manager import DeploymentsManager


class MockDeploymentsManager(DeploymentsManager):

    def __init__(self):
        self.calls = []
        self.deploy_raise_exception = False
        self.namespace_deployment_type_is_ready = {}
        self.namespace_deployment_type_hostname = {}
        self.hostname_verify_worker_access = {}
        self.all_releases = []
        self.prometheus_metrics = {}

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
