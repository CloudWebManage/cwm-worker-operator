import redis
from cwm_worker_operator import config
from cwm_worker_operator import metrics
import cwm_worker_deployment.deployment


def delete(domain_name, deployment_timeout_string=None):
    redis_pool = config.get_redis_pool()
    _metrics = metrics.Metrics("deleter", is_dummy=True)
    volume_config = config.get_cwm_api_volume_config(redis_pool, domain_name, _metrics)
    namespace_name = volume_config.get("hostname", domain_name).replace(".", "--")
    r = redis.Redis(connection_pool=redis_pool)
    config.del_worker_keys(r, domain_name)
    r.close()
    cwm_worker_deployment.deployment.delete(namespace_name, "minio", timeout_string=deployment_timeout_string)
