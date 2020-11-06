import urllib3
import requests
import traceback
from cwm_worker_operator import logs
from cwm_worker_operator import config
import cwm_worker_deployment.deployment
import cwm_worker_deployment.helm


urllib3.disable_warnings()


class DeploymentsManager:

    def __init__(self, cache_minio_versions=config.CACHE_MINIO_VERSIONS):
        self.cache_minio_versions = cache_minio_versions

    def init_cache(self):
        for version in self.cache_minio_versions:
            try:
                chart_path = cwm_worker_deployment.deployment.chart_cache_init("cwm-worker-deployment-minio", version, "minio")
                print("Initialized chart cache: {}".format(chart_path), flush=True)
            except Exception:
                traceback.print_exc()
                print("Failed to initialize chart cache for version {}".format(version))

    def init(self, deployment_config):
        cwm_worker_deployment.deployment.init(deployment_config)

    def deploy_external_service(self, deployment_config):
        cwm_worker_deployment.deployment.deploy_external_service(deployment_config)

    def deploy_extra_objects(self, deployment_config, extra_objects):
        cwm_worker_deployment.deployment.deploy_extra_objects(deployment_config, extra_objects)

    def deploy(self, deployment_config, **kwargs):
        cwm_worker_deployment.deployment.deploy(deployment_config, **kwargs)

    def is_ready(self, namespace_name, deployment_type):
        return cwm_worker_deployment.deployment.is_ready(namespace_name, deployment_type)

    def get_hostname(self, namespace_name, deployment_type):
        return cwm_worker_deployment.deployment.get_hostname(namespace_name, deployment_type)

    def verify_worker_access(self, hostname, log_kwargs):
        ok = True
        for proto in ["http", "https"]:
            url = {"http": "http://{}:8080".format(hostname), "https": "https://{}:8443".format(hostname)}[proto]
            requests_kwargs = {"http": {}, "https": {"verify": False}}[proto]
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=2, **requests_kwargs)
            except Exception as e:
                logs.debug("Failed {} readiness check".format(proto), debug_verbosity=3, exception=str(e), **log_kwargs)
                res = None
            if not res:
                ok = False
            elif res.status_code != 200:
                logs.debug("Failed {} readiness check".format(proto), debug_verbosity=3, status_code=res.status_code,
                           **log_kwargs)
                ok = False
            elif '<title>MinIO Browser</title>' not in res.text:
                logs.debug("Failed {} readiness check".format(proto), debug_verbosity=3, missing_title=True,
                           **log_kwargs)
                ok = False
        return ok

    def delete(self, namespace_name, deployment_type, **kwargs):
        cwm_worker_deployment.deployment.delete(namespace_name, deployment_type, **kwargs)

    def iterate_all_releases(self):
        for release in cwm_worker_deployment.helm.iterate_all_releases("minio"):
            yield release

    def get_worker_metrics(self, namespace_name):
        return cwm_worker_deployment.deployment.get_metrics(namespace_name, "minio")
