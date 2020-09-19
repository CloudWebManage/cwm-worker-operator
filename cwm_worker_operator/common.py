import traceback

from cwm_worker_operator import config
import cwm_worker_deployment.deployment


def init_cache():
    for version in config.CACHE_MINIO_VERSIONS:
        try:
            chart_path = cwm_worker_deployment.deployment.chart_cache_init("cwm-worker-deployment-minio", version, "minio")
            print("Initialized chart cache: {}".format(chart_path), flush=True)
        except Exception:
            traceback.print_exc()
            print("Failed to initialize chart cache for version {}".format(version))


def get_volume_config_namespace_from_domain(redis_pool, metrics, domain_name):
    volume_config = config.get_cwm_api_volume_config(redis_pool, domain_name, metrics)
    if volume_config.get("hostname"):
        return volume_config, volume_config["hostname"].replace(".", "--")
    else:
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
        return volume_config, None
