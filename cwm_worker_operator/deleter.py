import redis
from cwm_worker_operator import config
import cwm_worker_deployment.deployment


def delete(domain_name, deployment_timeout_string=None, delete_namespace=None, delete_helm=None):
    if delete_namespace is None:
        delete_namespace = config.DELETER_DEFAULT_DELETE_NAMESPACE
    if delete_helm is None:
        delete_helm = config.DELETER_DEFAULT_DELETE_HELM
    redis_pool = config.get_redis_pool()
    volume_config = config.get_cwm_api_volume_config(redis_pool, domain_name)
    namespace_name = volume_config.get("hostname", domain_name).replace(".", "--")
    r = redis.Redis(connection_pool=redis_pool)
    config.del_worker_keys(r, domain_name)
    r.close()
    cwm_worker_deployment.deployment.delete(
        namespace_name, "minio", timeout_string=deployment_timeout_string, delete_namespace=delete_namespace,
        delete_helm=delete_helm
    )
