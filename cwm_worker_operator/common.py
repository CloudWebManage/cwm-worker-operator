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
