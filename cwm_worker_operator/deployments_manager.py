import urllib3
import requests
import traceback
from cwm_worker_operator import logs
from cwm_worker_operator import config
import cwm_worker_deployment.helm

try:
    import cwm_worker_deployment.deployment
except Exception as e:
    if str(e) != 'Could not configure kubernetes python client':
        raise

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
        return cwm_worker_deployment.deployment.deploy(deployment_config, **kwargs)

    def is_ready(self, namespace_name, deployment_type):
        return cwm_worker_deployment.deployment.is_ready(namespace_name, deployment_type)

    def get_hostname(self, namespace_name, deployment_type):
        return {
            protocol: cwm_worker_deployment.deployment.get_hostname(namespace_name, deployment_type, protocol)
            for protocol in ['http', 'https']
        }

    def verify_worker_access(self, hostname, log_kwargs):
        ok = True
        for proto in ["http", "https"]:
            url = {"http": "http://{}:8080".format(hostname[proto]), "https": "https://{}:8443".format(hostname[proto])}[proto]
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

    def get_prometheus_metrics(self, namespace_name):
        metrics = {}
        for metric, prom_metric in {
            'cpu_seconds': 'container_cpu_usage_seconds_total',
            'ram_bytes': 'container_memory_usage_bytes'
        }.items():
            metrics[metric] = '0'
            try:
                res = requests.post('http://kube-prometheus-kube-prome-prometheus.monitoring:9090/api/v1/query', {
                    'query': 'sum(rate('+prom_metric+'{namespace="'+namespace_name+'"}[5m]))'
                }).json()
                if res.get('status') == 'success' and len(res.get('data', {}).get('result', [])) == 1:
                    metrics[metric] = str(res['data']['result'][0]['value'][1])
            except:
                traceback.print_exc()
        return metrics
