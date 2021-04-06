import os
import json
import time
import urllib3
import tempfile
import traceback
import subprocess
from contextlib import contextmanager

import requests
from ruamel import yaml

from cwm_worker_operator import logs
from cwm_worker_operator import config
import cwm_worker_deployment.helm
import cwm_worker_deployment.namespace
from cwm_worker_operator import common

try:
    import cwm_worker_deployment.deployment
except Exception as e:
    if str(e) != 'Could not configure kubernetes python client':
        raise

urllib3.disable_warnings()


class NodeCleanupPod:

    def __init__(self, namespace_name, pod_name, node_name):
        self.namespace_name = namespace_name
        self.pod_name = pod_name
        self.node_name = node_name

    def kubectl_create(self, pod):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pod.yaml"), "w") as f:
                yaml.safe_dump(pod, f)
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl create -f {}'.format(os.path.join(tmpdir, "pod.yaml")))
            assert ret == 0, out

    def kubectl_get_pod(self):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n {} get pod {} -o json'.format(self.namespace_name, self.pod_name))
        return json.loads(out) if ret == 0 else None

    def init(self):
        self.delete(wait=True)
        self.cordon()
        self.kubectl_create({
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.pod_name,
                "namespace": self.namespace_name
            },
            "spec": {
                'tolerations': [
                    {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"},
                    {"key": "node.kubernetes.io/unschedulable", "operator": "Exists", "effect": "NoSchedule"},
                ],
                "nodeSelector": {
                    "kubernetes.io/hostname": self.node_name
                },
                "containers": [
                    {
                        "name": "nodecleanup",
                        "image": "alpine",
                        "command": ["sh", "-c", "while true; do sleep 86400; done"],
                        "volumeMounts": [
                            {"name": "cache", "mountPath": "/cache"}
                        ]
                    }
                ],
                "volumes": [
                    {"name": "cache", "hostPath": {"path": "/remote/cache", "type": "DirectoryOrCreate"}}
                ]
            }
        })
        start_time = common.now()
        while True:
            pod = self.kubectl_get_pod()
            if pod:
                for condition in pod['status']['conditions']:
                    if condition['type'] == 'Ready' and condition['status'] == "True":
                        return
            else:
                assert (common.now() - start_time).total_seconds() <= 120, 'waited too long for node cleanup pod to be ready: {}'.format(pod)
            time.sleep(1)

    def cordon(self):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl cordon {}'.format(self.node_name))
        assert ret == 0, out

    def uncordon(self):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl uncordon {}'.format(self.node_name))
        assert ret == 0, out

    def delete(self, wait):
        subprocess.getstatusoutput('DEBUG= kubectl -n {} delete pod {} {}'.format(self.namespace_name, self.pod_name, "--wait" if wait else ""))

    def list_cache_namespaces(self):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n {} exec {} -- ls /cache'.format(self.namespace_name, self.pod_name))
        assert ret == 0, out
        return [s.strip() for s in out.split() if s and s.strip()]

    def clear_cache_namespace(self, cache_namespace_name):
        subprocess.check_call(['kubectl', '-n', self.namespace_name, 'exec', self.pod_name, '--', 'rm', '-rf', cache_namespace_name])


class DeploymentsManager:

    def __init__(self, cache_minio_versions=config.CACHE_MINIO_VERSIONS):
        self.cache_minio_versions = cache_minio_versions
        self.node_cleanup_pod_class = NodeCleanupPod

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
        for metric, prom_query_template in {
            'sum_cpu_seconds': 'sum(container_cpu_usage_seconds_total{namespace="NAMESPACE_NAME"})',
            'avg_ram_bytes_usage': 'sum(avg_over_time(container_memory_working_set_bytes{namespace="NAMESPACE_NAME"}[1m]))'
        }.items():
            metrics[metric] = '0'
            try:
                res = requests.post('http://kube-prometheus-kube-prome-prometheus.monitoring:9090/api/v1/query', {
                    'query': prom_query_template.replace('NAMESPACE_NAME', namespace_name)
                }).json()
                if res.get('status') == 'success' and len(res.get('data', {}).get('result', [])) == 1:
                    metrics[metric] = str(res['data']['result'][0]['value'][1])
            except:
                traceback.print_exc()
        return metrics

    def get_kube_metrics(self, namespace_name):
        return cwm_worker_deployment.namespace.get_kube_metrics(namespace_name)

    def iterate_cluster_nodes(self):
        ret, out = subprocess.getstatusoutput('kubectl get nodes -o custom-columns=name:metadata.name')
        assert ret == 0, out
        for node_name in out.splitlines()[1:]:
            node_name = node_name.strip()
            if node_name:
                ret, out = subprocess.getstatusoutput('kubectl get node {} -o json'.format(node_name))
                assert ret == 0, out
                node = json.loads(out)
                is_worker = False
                for taint in node.get('spec', {}).get('taints', []):
                    if taint.get('key') == 'cwmc-role'and taint.get('value') == 'worker':
                        is_worker = True
                        break
                unschedulable = bool(node.get('spec', {}).get('unschedulable'))
                yield {
                    'name': node_name,
                    'is_worker': is_worker,
                    'unschedulable': unschedulable
                }

    @contextmanager
    def node_cleanup_pod(self, node_name):
        ncp = self.node_cleanup_pod_class('default', 'cwm-worker-operator-node-cleanup', node_name)
        try:
            ncp.init()
            yield ncp
        finally:
            ncp.uncordon()
            ncp.delete(wait=False)
