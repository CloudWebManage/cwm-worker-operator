import os
import uuid
import json
import time
import boto3
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


NODE_CLEANER_CORDON_LABEL = 'cwmc-cleaner-cordon'


def kubectl_create(obj):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "obj.yaml"), "w") as f:
            yaml.safe_dump(obj, f)
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default create -f {}'.format(os.path.join(tmpdir, "obj.yaml")))
        assert ret == 0, out


class NodeCleanupPod:

    def __init__(self, namespace_name, pod_name, node_name):
        self.namespace_name = namespace_name
        self.pod_name = pod_name
        self.node_name = node_name

    def kubectl_get_pod(self):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n {} get pod {} -o json'.format(self.namespace_name, self.pod_name))
        return json.loads(out) if ret == 0 else None

    def kubectl_create(self, obj):
        kubectl_create(obj)

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
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl label --overwrite node {} {}=yes'.format(self.node_name, NODE_CLEANER_CORDON_LABEL))
        assert ret == 0, out
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl cordon {}'.format(self.node_name))
        assert ret == 0, out

    def uncordon(self):
        DeploymentsManager().node_cleaner_uncordon_node(self.node_name)

    def delete(self, wait):
        subprocess.getstatusoutput('DEBUG= kubectl -n {} delete pod {} {}'.format(self.namespace_name, self.pod_name, "--wait" if wait else ""))

    def list_cache_namespaces(self):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n {} exec {} -- ls /cache'.format(self.namespace_name, self.pod_name))
        assert ret == 0, out
        return [s.strip().replace('minio-', '').replace('nginx-', '') for s in out.split() if s and s.strip()]

    def clear_cache_namespace(self, cache_namespace_name):
        if len(cache_namespace_name) > 1:
            subprocess.check_output(
                ['kubectl', '-n', self.namespace_name, 'exec', self.pod_name, '--', 'rm', '-rf', os.path.join("/cache", 'minio-{}'.format(cache_namespace_name))],
                env={**os.environ, "DEBUG": ""}
            )
            subprocess.check_output(
                ['kubectl', '-n', self.namespace_name, 'exec', self.pod_name, '--', 'rm', '-rf', os.path.join("/cache", 'nginx-{}'.format(cache_namespace_name))],
                env={**os.environ, "DEBUG": ""}
            )


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

    def is_ready(self, namespace_name, deployment_type, minimal_check=False):
        return cwm_worker_deployment.deployment.is_ready(namespace_name, deployment_type, minimal_check=minimal_check)

    def get_hostname(self, namespace_name, deployment_type):
        return {
            protocol: cwm_worker_deployment.deployment.get_hostname(namespace_name, deployment_type, protocol)
            for protocol in ['http', 'https']
        }

    def verify_worker_access(self, internal_hostname, log_kwargs, path='/minio/health/live', check_hostname_challenge=None):
        internal_hostname = internal_hostname['http']
        if check_hostname_challenge:
            path = '/.well-known/acme-challenge/{}'.format(check_hostname_challenge['token'])
            headers = {'Host': check_hostname_challenge['host']}
        else:
            headers = None
        url = "http://{}:8080{}".format(internal_hostname, path)
        try:
            res = requests.get(url, timeout=2, headers=headers)
        except Exception as e:
            logs.debug("Failed readiness check", debug_verbosity=3, exception=str(e), **log_kwargs)
            res = None
        if not res:
            return False
        elif res.status_code != 200:
            logs.debug("Failed readiness check", debug_verbosity=3, status_code=res.status_code, **log_kwargs)
            return False
        elif check_hostname_challenge:
            return res.text.strip() == check_hostname_challenge['payload'].strip()
        else:
            return True

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
                public_ip = node.get('status', {}).get('addresses', [{}])[0].get('address', '')
                labels = node.get('metadata', {}).get('labels', {})
                yield {
                    'name': node_name,
                    'is_worker': is_worker,
                    'unschedulable': unschedulable,
                    'public_ip': public_ip,
                    'cleaner_cordoned': labels.get(NODE_CLEANER_CORDON_LABEL) == 'yes'
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

    def node_cleaner_uncordon_node(self, node_name):
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl label node {} {}-'.format(node_name, NODE_CLEANER_CORDON_LABEL))
        assert ret == 0, out
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl uncordon {}'.format(node_name))
        assert ret == 0, out

    def worker_has_pod_on_node(self, namespace_name, node_name):
        ret, out = subprocess.getstatusoutput('kubectl get pods -n {} -ocustom-columns=node:spec.nodeName | tail -n +2 | grep \'^{}$\''.format(namespace_name, node_name))
        return ret == 0

    def iterate_dns_healthchecks(self):
        client = boto3.client('route53')
        next_marker = ''
        while True:
            res = client.list_health_checks(Marker=next_marker)
            for healthcheck in res.get('HealthChecks', []):
                healthcheck_id = healthcheck['Id']
                healthcheck_name = None
                for tag in client.list_tags_for_resource(ResourceType='healthcheck', ResourceId=healthcheck_id)['ResourceTagSet']['Tags']:
                    if tag['Key'] == 'Name':
                        healthcheck_name = tag['Value']
                        break
                healthcheck_ip = healthcheck.get('HealthCheckConfig', {}).get('IPAddress') or ''
                if healthcheck_name and healthcheck_name.startswith(config.DNS_RECORDS_PREFIX + ":"):
                    yield {
                        'id': healthcheck_id,
                        'node_name': healthcheck_name.replace(config.DNS_RECORDS_PREFIX + ":", ""),
                        'ip': healthcheck_ip
                    }
            if res['IsTruncated']:
                next_marker = res['NextMarker']
            else:
                break

    def iterate_dns_records(self):
        client = boto3.client('route53')
        next_record_identifier = None
        while True:
            res = client.list_resource_record_sets(
                HostedZoneId=config.AWS_ROUTE53_HOSTEDZONE_ID,
                **({'StartRecordIdentifier': next_record_identifier} if next_record_identifier is not None else {})
            )
            for record in res.get('ResourceRecordSets', []):
                if record['Type'] == 'A' and record['Name'] == '{}.{}.'.format(config.DNS_RECORDS_PREFIX, config.AWS_ROUTE53_HOSTEDZONE_DOMAIN):
                    if record['SetIdentifier'].startswith(config.DNS_RECORDS_PREFIX+':'):
                        record_ip = ''
                        for value in record.get('ResourceRecords', []):
                            record_ip = value.get('Value') or ''
                            break
                        yield {
                            'id': json.dumps(record),
                            'node_name': record['SetIdentifier'].replace(config.DNS_RECORDS_PREFIX+':', ''),
                            'ip': record_ip
                        }
            if res['IsTruncated']:
                next_record_identifier = res['NextRecordIdentifier']
            else:
                break

    def set_dns_healthcheck(self, node_name, node_ip):
        client = boto3.client('route53')
        caller_reference = str(uuid.uuid4())
        res = client.create_health_check(
            CallerReference=caller_reference,
            HealthCheckConfig={
                "IPAddress": node_ip,
                "Port": 80,
                "Type": "HTTP",
                "ResourcePath": "/healthz",
                "RequestInterval": 30,  # according to AWS docs, when using the recommended regions, it actually does a healthcheck every 2-3 seconds
                "FailureThreshold": 1,
            }
        )
        healthcheck_id = res['HealthCheck']['Id']
        client.change_tags_for_resource(
            ResourceType="healthcheck",
            ResourceId=healthcheck_id,
            AddTags=[
                {"Key": "Name", "Value": config.DNS_RECORDS_PREFIX + ":" + node_name}
            ]
        )
        return healthcheck_id

    def set_dns_record(self, node_name, node_ip, healthcheck_id):
        client = boto3.client('route53')
        client.change_resource_record_sets(
            HostedZoneId=config.AWS_ROUTE53_HOSTEDZONE_ID,
            ChangeBatch={
                "Comment": "cwm-worker-operator deployments_manager.set_dns_record({},{})".format(node_name, node_ip),
                "Changes": [
                    {
                        "Action": "CREATE",
                        "ResourceRecordSet": {
                            "Name": '{}.{}.'.format(config.DNS_RECORDS_PREFIX, config.AWS_ROUTE53_HOSTEDZONE_DOMAIN),
                            'Type': 'A',
                            'SetIdentifier': config.DNS_RECORDS_PREFIX + ':' + node_name,
                            'MultiValueAnswer': True,
                            'TTL': 120,
                            'ResourceRecords': [
                                {
                                    'Value': node_ip
                                }
                            ],
                            'HealthCheckId': healthcheck_id
                        }
                    }
                ]
            }
        )

    def delete_dns_healthcheck(self, healthcheck_id):
        client = boto3.client('route53')
        client.delete_health_check(HealthCheckId=healthcheck_id)

    def delete_dns_record(self, record_id):
        client = boto3.client('route53')
        record = json.loads(record_id)
        client.change_resource_record_sets(
            HostedZoneId=config.AWS_ROUTE53_HOSTEDZONE_ID,
            ChangeBatch={
                "Comment": "cwm-worker-operator deployments_manager.delete_dns_record",
                "Changes": [
                    {
                        "Action": "DELETE",
                        "ResourceRecordSet": record
                    }
                ]
            }
        )

    def iterate_minio_nginx_pods_on_node(self, node_name):
        for pod in json.loads(subprocess.check_output([
            'kubectl', 'get', 'pods', '--all-namespaces', '--field-selector=spec.nodeName={}'.format(node_name), '-lapp=minio-nginx', '-ojson'
        ]))['items']:
            if not pod['metadata']['name'].startswith('minio-nginx-'):
                continue
            if pod['spec']['containers'][0]['name'] != 'nginx':
                continue
            yield pod['metadata']['namespace'], pod['metadata']['name']

    def pod_exec(self, namespace_name, pod_name, *args):
        return subprocess.check_output(['kubectl', '-n', namespace_name, 'exec', pod_name, '--', *args])

    def check_node_nas(self, node_name):
        pod_name = 'check-node-nas'
        logs.debug('starting check_node_nas', debug_verbosity=8, node_name=node_name)
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default get pod {}'.format(pod_name))
        if ret == 0:
            logs.debug('deleting existing pod', debug_verbosity=8, node_name=node_name)
            subprocess.getstatusoutput('DEBUG= kubectl -n default delete pod {} --wait'.format(pod_name))
        logs.debug('creating pod', debug_verbosity=8, node_name=node_name)
        kubectl_create({
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "namespace": 'default'
            },
            "spec": {
                'tolerations': [
                    {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"}
                ],
                "nodeSelector": {
                    "kubernetes.io/hostname": node_name
                },
                "containers": [
                    {
                        "name": "naschecker",
                        "image": "alpine",
                        "command": ["sh", "-c", "while true; do sleep 86400; done"],
                        "volumeMounts": [
                            {
                                "name": "nas{}".format(i),
                                "mountPath": "/mnt/nas{}".format(i)
                            }
                            for i, nas_ip in enumerate(config.NAS_IPS)
                        ]
                    }
                ],
                "volumes": [
                    {
                        "name": "nas{}".format(i),
                        **json.loads(config.NAS_CHECKER_VOLUME_TEMPLATE_JSON.replace('__NAS_IP__', nas_ip))
                    }
                    for i, nas_ip in enumerate(config.NAS_IPS)
                ]
            }
        })
        logs.debug('waiting for pod mounts to be ready', debug_verbosity=8, node_name=node_name)
        start_time = common.now()
        node_nas_health = {nas_ip: False for nas_ip in config.NAS_IPS}
        while True:
            time.sleep(5)
            for i, nas_ip in enumerate(config.NAS_IPS):
                if not node_nas_health[nas_ip]:
                    ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec {} ls /mnt/nas{}'.format(pod_name, i))
                    if ret != 0:
                        logs.debug("Error running ls: {}".format(out), debug_verbosity=8, node_name=node_name, nas_ip=nas_ip)
                        break
                    ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec {} touch /mnt/nas{}/check_node_nas_health'.format(pod_name, i))
                    if ret != 0:
                        logs.debug("Error creating file: {}".format(out), debug_verbosity=8, node_name=node_name, nas_ip=nas_ip)
                        break
                    node_nas_health[nas_ip] = True
            if all([v for k, v in node_nas_health.items()]):
                break
            elif (common.now() - start_time).total_seconds() > 60:
                break
        logs.debug('deleting pod', debug_verbosity=8, node_name=node_name)
        subprocess.getstatusoutput('DEBUG= kubectl -n default delete pod {} --wait'.format(pod_name))
        return node_nas_health
