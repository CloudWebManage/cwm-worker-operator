import os
import uuid
import json
import time
import boto3
import urllib3
import tempfile
import datetime
import traceback
import subprocess
from contextlib import contextmanager

import requests
from ruamel import yaml
from minio.minioadmin import MinioAdmin
from minio.credentials.providers import StaticProvider
from minio import Minio

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
# Pulled Dec 29, 2021
ALPINE_IMAGE = "alpine:3.15.0@sha256:21a3deaa0d32a8057914f36584b5288d2e5ecc984380bc0118285c70fa8c9300"


def kubectl_create(obj, namespace_name='default'):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "obj.yaml"), "w") as f:
            yaml.safe_dump(obj, f)
        ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n {} create -f {}'.format(
            namespace_name, os.path.join(tmpdir, "obj.yaml")))
        assert ret == 0, out


def parse_datetime_from_kubelet_log_line(line):
    # I0112 14:54:20.399101
    datepart, timepart, *_ = line.split()
    return datetime.datetime.strptime('{}{} {}+00:00'.format(datetime.datetime.now().year, datepart, timepart), '%YI%m%d %H:%M:%S.%f%z')


def get_minio_admin():
    return MinioAdmin(
        config.MINIO_TENANT_ENDPOINT,
        StaticProvider(config.MINIO_TENANT_ADMIN_USER, config.MINIO_TENANT_ADMIN_PASSWORD)
    )


def get_minio():
    return Minio(config.MINIO_TENANT_ENDPOINT, config.MINIO_TENANT_ADMIN_USER, config.MINIO_TENANT_ADMIN_PASSWORD)


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
                        "image": ALPINE_IMAGE,
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
        pass
        # cwm_worker_deployment.deployment.init(deployment_config)

    def deploy_external_service(self, deployment_config):
        pass
        # cwm_worker_deployment.deployment.deploy_external_service(deployment_config)

    def deploy_extra_objects(self, deployment_config, extra_objects):
        pass
        # cwm_worker_deployment.deployment.deploy_extra_objects(deployment_config, extra_objects)

    def deploy_preprocess_specs(self, specs):
        res = {}
        for key, spec in specs.items():
            # currently we don't have any preprocess spec, but we should set True to prevent re-preprocessing
            res[key] = True
        return res

    def deploy(self, deployment_config, dry_run=False, **kwargs):
        # return cwm_worker_deployment.deployment.deploy(deployment_config, **kwargs)
        username = deployment_config['cwm-worker-deployment']['namespace']
        password = deployment_config['minio']['access_key']
        if dry_run:
            return f"username: {username}"
        else:
            minio_admin = get_minio_admin()
            minio_admin.user_add(username, password)
            with tempfile.NamedTemporaryFile('w') as f:
                json.dump({
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": ["s3:*"],
                            "Effect": "Allow",
                            "Resource": [f"arn:aws:s3:::{username}",f"arn:aws:s3:::{username}/*"]
                        },
                        {
                            "Action": ["s3:DeleteBucket"],
                            "Effect": "Deny",
                            "Resource": [f"arn:aws:s3:::{username}"]
                        },
                        {
                            "Action": ["s3:ListAllMyBuckets"],
                            "Effect": "Allow",
                            "Resource": ["arn:aws:s3:::*"]
                        }
                    ]
                }, f)
                f.seek(0)
                minio_admin.policy_add(username, f.name)
            minio_admin.policy_set(username, username)
            minio = get_minio()
            if not minio.bucket_exists(username):
                minio.make_bucket(username)
            return f"OK, username/bucket: {username}"

    def is_ready(self, namespace_name, deployment_type, minimal_check=False):
        #return cwm_worker_deployment.deployment.is_ready(namespace_name, deployment_type, minimal_check=minimal_check)
        return get_minio().bucket_exists(namespace_name)

    def get_health(self, namespace_name, deployment_type):
        return cwm_worker_deployment.deployment.get_health(namespace_name, deployment_type)

    def get_all_namespaces(self):
        ret, out = subprocess.getstatusoutput("kubectl get ns --no-headers -o=custom-columns=NAME:.metadata.name")
        assert ret == 0, out
        return [line.strip() for line in out.splitlines() if line.strip()]

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
        for username, user in json.loads(get_minio_admin().user_list()).items():
            yield {'username': username, 'user': user}

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
                }, timeout=15).json()
                if res.get('status') == 'success' and len(res.get('data', {}).get('result', [])) == 1:
                    metrics[metric] = str(res['data']['result'][0]['value'][1])
            except:
                traceback.print_exc()
        return metrics

    def get_kube_metrics(self, namespace_name):
        return cwm_worker_deployment.namespace.get_kube_metrics(namespace_name)

    def iterate_cluster_worker_nodes(self):
        return (node for node in self.iterate_cluster_nodes() if node['is_worker'])

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
        ret, _ = subprocess.getstatusoutput('kubectl get pods -n {} -ocustom-columns=node:spec.nodeName | tail -n +2 | grep \'^{}$\''.format(namespace_name, node_name))
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
        next_record_identifier, next_record_name, next_record_type = None, None, None
        while True:
            res = client.list_resource_record_sets(
                HostedZoneId=config.AWS_ROUTE53_HOSTEDZONE_ID,
                **({'StartRecordIdentifier': next_record_identifier} if next_record_identifier is not None else {}),
                **({'StartRecordName': next_record_name} if next_record_name is not None else {}),
                **({'StartRecordType': next_record_type} if next_record_type is not None else {}),
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
                next_record_identifier = res.get('NextRecordIdentifier')
                next_record_name = res.get('NextRecordName')
                next_record_type = res.get('NextRecordType')
            else:
                break

    def set_dns_healthcheck(self, node_name, node_ip):
        client = boto3.client('route53')
        caller_reference = str(uuid.uuid4())
        res = client.create_health_check(
            CallerReference=caller_reference,
            HealthCheckConfig={
                "IPAddress": node_ip,
                "Port": 12808,
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

    def check_nodes_nas_update_kubelet_logs(self, node_names, nodes_pod_names, nodes_nas_ip_statuses):
        for node_name in node_names:
            for pod_name, nas_ip in nodes_pod_names[node_name].items():
                nodes_nas_ip_statuses[node_name][nas_ip]['mount_duration_seconds'] = None
                mount_duration_errors = []
                try:
                    ret, out = subprocess.getstatusoutput(
                        'DEBUG= kubectl -n {} exec {} -- chroot /host docker logs --tail 2000 kubelet'.format(
                            config.NAS_CHECKER_NAMESPACE, pod_name))
                    kubelet_log_lines = out.splitlines() if ret == 0 else None
                    if not kubelet_log_lines:
                        mount_duration_errors.append("failed to get kubelet log lines")
                    ret, out = subprocess.getstatusoutput(
                        'DEBUG= kubectl -n {} get pod {} -o json'.format(
                            config.NAS_CHECKER_NAMESPACE, pod_name))
                    pod_uid = json.loads(out)['metadata']['uid'] if ret == 0 else None
                    if not pod_uid:
                        mount_duration_errors.append("failed to get pod uid")
                    if kubelet_log_lines and pod_uid:
                        start_mount_datetime, end_mount_datetime = None, None
                        for line in reversed(kubelet_log_lines):
                            if pod_uid in line:
                                if 'operationExecutor.MountVolume started for volume "nas"' in line:
                                    start_mount_datetime = parse_datetime_from_kubelet_log_line(line)
                                elif 'MountVolume.SetUp succeeded for volume "nas"' in line:
                                    end_mount_datetime = parse_datetime_from_kubelet_log_line(line)
                        if not start_mount_datetime:
                            mount_duration_errors.append("failed to find start mount log line")
                        elif not end_mount_datetime:
                            mount_duration_errors.append("failed to find end mount log line")
                        elif end_mount_datetime <= start_mount_datetime:
                            mount_duration_errors.append("end mount datetime is smaller or equal to start mount datetime")
                        elif (common.now() - end_mount_datetime).total_seconds() > 120:
                            mount_duration_errors.append("end mount datetime is more then 120 seconds ago")
                        else:
                            nodes_nas_ip_statuses[node_name][nas_ip]['mount_duration_seconds'] = (end_mount_datetime - start_mount_datetime).total_seconds()
                except:
                    exc = traceback.format_exc()
                    print(exc)
                    mount_duration_errors.append(exc)
                if len(mount_duration_errors) > 0:
                    nodes_nas_ip_statuses[node_name][nas_ip]['is_healthy'] = False
                    nodes_nas_ip_statuses[node_name][nas_ip]['mount_duration_errors'] = ', '.join(mount_duration_errors)
                else:
                    nodes_nas_ip_statuses[node_name][nas_ip]['mount_duration_errors'] = ''

    def check_nodes_nas(self, node_names, with_kubelet_logs=False, overrides_callback=None,
                        timeout_seconds_per_node_pod=3):
        logs.debug('starting check_nodes_nas', debug_verbosity=8, node_names=node_names)
        logs.debug('deleting existing pods', debug_verbosity=8)
        if overrides_callback:
            print("WARNING! using overrides_callback")
        else:
            overrides_callback = lambda operation, data, default_res: default_res
        ret, out = subprocess.getstatusoutput(
            'kubectl -n {} delete pods -l app=cwm-worker-operator-check-node-nas --wait --timeout 60s'.format(
                config.NAS_CHECKER_NAMESPACE)
        )
        if ret != 0:
            logs.debug_info('failed to delete pods, continuing anyway', ret=ret, out=out)
        nodes_nas_ip_statuses = {
            node_name: {
                nas_ip: {'is_healthy': False, 'log': []} for nas_ip in config.NAS_IPS
            } for node_name in node_names
        }

        def log(node_name, nas_ip, step, **data):
            nodes_nas_ip_statuses[node_name][nas_ip]['log'].append({'step': step, 'dt': common.now().strftime('%Y-%m-%d %H:%M:%S'), **data})

        nodes_pod_names = {
            node_name: {
                'check-node-nas-{}-{}'.format(node_i, pod_i): nas_ip for pod_i, nas_ip in enumerate(config.NAS_IPS)
            } for node_i, node_name in enumerate(node_names)
        }
        for node_name in node_names:
            for pod_name, nas_ip in nodes_pod_names[node_name].items():
                log(node_name, nas_ip, 'start', pod_name=pod_name)
        logs.debug('creating pods', debug_verbosity=8)
        for node_name in node_names:
            for pod_name, nas_ip in nodes_pod_names[node_name].items():
                log(node_name, nas_ip, 'start kubectl_create')
                try:
                    kubectl_create({
                        "apiVersion": "v1",
                        "kind": "Pod",
                        "metadata": {
                            "name": pod_name,
                            "namespace": config.NAS_CHECKER_NAMESPACE,
                            'labels': {
                                'app': 'cwm-worker-operator-check-node-nas'
                            }
                        },
                        "spec": {
                            'tolerations': [
                                {"key": "cwmc-role", "operator": "Exists", "effect": "NoSchedule"}
                            ],
                            "nodeSelector": overrides_callback(
                                'nodeSelector', {'node_name': node_name},
                                {
                                    "kubernetes.io/hostname": node_name
                                }
                            ),
                            "containers": [
                                {
                                    "name": "naschecker",
                                    "image": ALPINE_IMAGE,
                                    "command": ["sh", "-c", "while true; do sleep 86400; done"],
                                    "volumeMounts": [
                                        {
                                            "name": "nas",
                                            "mountPath": "/mnt/nas"
                                        },
                                        *([{
                                            "name": "hostfs",
                                            "mountPath": "/host"
                                        }] if with_kubelet_logs else [])
                                    ]
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "nas",
                                    **json.loads(config.NAS_CHECKER_VOLUME_TEMPLATE_JSON.replace('__NAS_IP__', nas_ip))
                                },
                                *([{
                                    "name": "hostfs",
                                    "hostPath": {"path": "/"}
                                }] if with_kubelet_logs else [])
                            ]
                        }
                    }, namespace_name=config.NAS_CHECKER_NAMESPACE)
                    nodes_nas_ip_statuses[node_name][nas_ip]['kubectl_create_success'] = True
                    log(node_name, nas_ip, 'end kubectl_create', success=True)
                except:
                    nodes_nas_ip_statuses[node_name][nas_ip]['kubectl_create_success'] = False
                    log(node_name, nas_ip, 'end kubectl_create', success=False, error=traceback.format_exc())
        logs.debug('waiting for pod mounts to be ready', debug_verbosity=8)
        start_time = common.now()
        timeout_seconds = 0
        for node_name in node_names:
            timeout_seconds += len(nodes_pod_names[node_name]) * timeout_seconds_per_node_pod
        while True:
            time.sleep(5)
            timeout_msg = None
            for node_name in node_names:
                for pod_name, nas_ip in nodes_pod_names[node_name].items():
                    if not nodes_nas_ip_statuses[node_name][nas_ip]['is_healthy']:
                        ls_cmd = overrides_callback(
                            'get_ls_cmd', {'pod_name': pod_name, 'node_name': node_name, 'namespace': config.NAS_CHECKER_NAMESPACE},
                            'DEBUG= kubectl -n {} exec {} -- ls /mnt/nas'.format(config.NAS_CHECKER_NAMESPACE, pod_name)
                        )
                        ret, out = subprocess.getstatusoutput(ls_cmd)
                        if ret != 0:
                            log(node_name, nas_ip, 'wait_ready_ls', ret=ret, out=out)
                            logs.debug("Error running ls: {}".format(out), debug_verbosity=8, node_name=node_name, nas_ip=nas_ip)
                        elif (common.now() - start_time).total_seconds() > timeout_seconds:
                            log(node_name, nas_ip, 'wait_ready_ls', timeout=True)
                            logs.debug("Timed out waiting for ls", debug_verbosity=8, node_name=node_name, nas_ip=nas_ip)
                        else:
                            ret, out = subprocess.getstatusoutput(
                                'DEBUG= kubectl -n {} exec {} -- touch /mnt/nas/check_node_nas_health'.format(
                                    config.NAS_CHECKER_NAMESPACE, pod_name))
                            if ret != 0:
                                log(node_name, nas_ip, 'wait_ready_touch', ret=ret, out=out)
                                logs.debug("Error creating file: {}".format(out), debug_verbosity=8, node_name=node_name, nas_ip=nas_ip)
                            elif (common.now() - start_time).total_seconds() > timeout_seconds:
                                log(node_name, nas_ip, 'wait_ready_touch', timeout=True)
                                logs.debug("Timed out waiting for touch", debug_verbosity=8, node_name=node_name, nas_ip=nas_ip)
                            else:
                                nodes_nas_ip_statuses[node_name][nas_ip]['is_healthy'] = True
                    if (common.now() - start_time).total_seconds() > timeout_seconds:
                        if not timeout_msg:
                            timeout_msg = f'timeout in node {node_name} nas_ip {nas_ip}'
                        break
                    if not nodes_nas_ip_statuses[node_name][nas_ip]['is_healthy']:
                        ret, out = subprocess.getstatusoutput(
                            'DEBUG= kubectl -n {} get pod {} -o yaml'.format(
                                config.NAS_CHECKER_NAMESPACE, pod_name))
                        log(node_name, nas_ip, 'wait_ready_failed', ret=ret, out=out)
                if (common.now() - start_time).total_seconds() > timeout_seconds:
                    if not timeout_msg:
                        timeout_msg = f'timeout in node {node_name}'
                    break
            num_not_healthy = 0
            for node_name in node_names:
                for pod_name, nas_ip in nodes_pod_names[node_name].items():
                    if not nodes_nas_ip_statuses[node_name][nas_ip]['is_healthy']:
                        num_not_healthy += 1
                        if timeout_msg:
                            log(node_name, nas_ip, 'timeout', timeout_msg=timeout_msg)
            if num_not_healthy == 0:
                break
            elif (common.now() - start_time).total_seconds() > timeout_seconds:
                break
            logs.debug('some node pods are not healthy yet', debug_verbosity=8, num_not_healthy=num_not_healthy)
        if with_kubelet_logs:
            self.check_nodes_nas_update_kubelet_logs(node_names, nodes_pod_names, nodes_nas_ip_statuses)
        logs.debug('deleting pods', debug_verbosity=8)
        ret, out = subprocess.getstatusoutput(
            'kubectl -n {} delete pods -l app=cwm-worker-operator-check-node-nas --wait --timeout 60s'.format(
                config.NAS_CHECKER_NAMESPACE)
        )
        if ret != 0:
            logs.debug_info('failed to delete pods, continuing anyway', ret=ret, out=out)
        return nodes_nas_ip_statuses
