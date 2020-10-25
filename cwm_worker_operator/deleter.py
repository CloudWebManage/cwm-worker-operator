from cwm_worker_operator import config
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


def delete(domain_name, deployment_timeout_string=None, delete_namespace=None, delete_helm=None,
           domains_config=None, deployments_manager=None):
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    if delete_namespace is None:
        delete_namespace = config.DELETER_DEFAULT_DELETE_NAMESPACE
    if delete_helm is None:
        delete_helm = config.DELETER_DEFAULT_DELETE_HELM
    volume_config = domains_config.get_cwm_api_volume_config(domain_name)
    namespace_name = volume_config.get("hostname", domain_name).replace(".", "--")
    domains_config.del_worker_keys(None, domain_name)
    deployments_manager.delete(
        namespace_name, "minio", timeout_string=deployment_timeout_string, delete_namespace=delete_namespace,
        delete_helm=delete_helm
    )
