import os
import json
import time
import pytz
import shutil
import pytest
import datetime
import subprocess

from cwm_worker_operator import common
from cwm_worker_operator.deployments_manager import DeploymentsManager


def test_init_cache():
    cache_minio_version = '0.0.0-20200829T091900'
    helm_cache_dir = os.environ.get("CWM_WORKER_DEPLOYMENT_HELM_CACHE_DIR") or "/var/cache/cwm-worker-deployment-helm-cache"
    cache_dir = os.path.join(helm_cache_dir, 'cwm-worker-deployment-minio', cache_minio_version)
    shutil.rmtree(cache_dir, ignore_errors=True)
    with pytest.raises(FileNotFoundError):
        os.stat(os.path.join(cache_dir, 'cwm-worker-deployment-minio'))
    DeploymentsManager(cache_minio_versions=[cache_minio_version]).init_cache()
    os.stat(os.path.join(cache_dir, 'cwm-worker-deployment-minio'))


def test_deploy():
    # prompf = subprocess.Popen('exec kubectl port-forward service/prometheus-kube-prometheus-prometheus 9090', shell=True)
    # try:
    namespace_name = 'example007--com'
    returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
    if returncode == 0:
        returncode, _ = subprocess.getstatusoutput('kubectl delete ns {}'.format(namespace_name))
        assert returncode == 0
    returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
    assert returncode == 1
    deployments_manager = DeploymentsManager()
    deployment_config = {
        'cwm-worker-deployment': {
            'type': 'minio',
            'namespace': namespace_name
        },
        'minio': {},
        'extraObjects': []
    }
    deployments_manager.init(deployment_config)
    returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
    assert returncode == 0
    deployments_manager.init(deployment_config)
    returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
    assert returncode == 0
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get service test-extra-object'.format(namespace_name))
    assert returncode == 1
    deployments_manager.deploy_extra_objects(deployment_config, [{
        'apiVersion': 'v1',
        'kind': 'Service',
        'name': 'test-extra-object',
        'spec': 'ports:\n- name: "8080"\n  port: 8080\n  TargetPort: 8080\nselector:\n  app: minio-server'}])
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get service test-extra-object'.format(namespace_name))
    assert returncode == 0
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-server'.format(namespace_name))
    assert returncode == 1
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-logger'.format(namespace_name))
    assert returncode == 1
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-nginx'.format(namespace_name))
    assert returncode == 1
    print("Deploying...")
    deployments_manager.deploy(deployment_config, with_init=False, atomic_timeout_string='2m')
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-server'.format(namespace_name))
    assert returncode == 0
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-logger'.format(namespace_name))
    assert returncode == 0
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-nginx'.format(namespace_name))
    assert returncode == 0
    start_time = datetime.datetime.now(pytz.UTC)
    while not deployments_manager.is_ready(namespace_name, 'minio'):
        time.sleep(1)
        if (datetime.datetime.now(pytz.UTC) - start_time).total_seconds() > 30:
            raise Exception("Waited too long for deployment to be ready")
    ingress_hostname = deployments_manager.get_hostname(namespace_name, 'minio')
    assert ingress_hostname == {
        'http': 'minio-nginx.{}.svc.cluster.local'.format(namespace_name),
        'https': 'minio-nginx.{}.svc.cluster.local'.format(namespace_name),
    }
    all_releases = {r['namespace']: r for r in deployments_manager.iterate_all_releases()}
    assert namespace_name in all_releases
    nginx_pod_names = []
    for _node in deployments_manager.iterate_cluster_nodes():
        for _namespace_name, _pod_name in deployments_manager.iterate_minio_nginx_pods_on_node(_node['name']):
            if _namespace_name == namespace_name:
                nginx_pod_names.append(_pod_name)
    assert len(nginx_pod_names) == 1
    nginx_pod_name = nginx_pod_names[0]
    assert set(deployments_manager.pod_exec(namespace_name, nginx_pod_name, 'bash', '-c', 'for FILE in /var/cache/nginx/minio/*; do echo $FILE; done').decode().splitlines()) == {
        '/var/cache/nginx/minio/cache', '/var/cache/nginx/minio/temp'
    }
    deployments_manager.delete(namespace_name, 'minio', delete_helm=False, delete_namespace=False)
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-server'.format(namespace_name))
    assert returncode == 1
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-logger'.format(namespace_name))
    assert returncode == 1
    returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio-nginx'.format(namespace_name))
    assert returncode == 1
    returncode, _ = subprocess.getstatusoutput('helm -n {0} get all minio-{0}'.format(namespace_name))
    assert returncode == 0
    deployments_manager.delete(namespace_name, 'minio', delete_helm=True, delete_namespace=False)
    returncode, _ = subprocess.getstatusoutput('helm -n {0} get all minio-{0}'.format(namespace_name))
    assert returncode == 1
    deployments_manager.delete(namespace_name, 'minio', delete_helm=True, delete_namespace=True)
    start_time = datetime.datetime.now(pytz.UTC)
    while True:
        returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
        if returncode == 1:
            break
        if (datetime.datetime.now(pytz.UTC) - start_time).total_seconds() > 60:
            raise Exception("Waited too long for namespace to be deleted")
    # finally:
    #     prompf.terminate()


@pytest.mark.filterwarnings("ignore:Unverified HTTPS request.*")
def test_verify_worker_access():
    subprocess.getstatusoutput('docker rm -f mocknginx')
    returncode, _ = subprocess.getstatusoutput('docker build -t mocknginx tests/mocks/nginx && docker run -p 8080:80 -d --name mocknginx mocknginx')
    assert returncode == 0
    time.sleep(5)
    assert DeploymentsManager().verify_worker_access({
        'http': 'localhost',
        'https': 'localhost'
    }, {}, path='/')


def test_iterate_cluster_nodes():
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl get node minikube -o json')
    assert ret == 0, out
    node = json.loads(out)
    node_ip = node['status']['addresses'][0]['address']
    deployments_manager = DeploymentsManager()
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl label --overwrite node minikube cwmc-cleaner-cordon=yes')
    assert ret == 0, out
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl taint node minikube cwmc-role-; DEBUG= kubectl uncordon minikube')
    assert ret == 0, out
    assert list(deployments_manager.iterate_cluster_nodes()) == [{'is_worker': False, 'name': 'minikube', 'unschedulable': False, 'public_ip': node_ip,
                                                                  'cleaner_cordoned': True}]
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl taint node minikube cwmc-role=worker:NoSchedule')
    assert ret == 0, out
    assert list(deployments_manager.iterate_cluster_nodes()) == [{'is_worker': True, 'name': 'minikube', 'unschedulable': False, 'public_ip': node_ip,
                                                                  'cleaner_cordoned': True}]
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl cordon minikube')
    assert ret == 0, out
    assert list(deployments_manager.iterate_cluster_nodes()) == [{'is_worker': True, 'name': 'minikube', 'unschedulable': True, 'public_ip': node_ip,
                                                                  'cleaner_cordoned': True}]
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl taint node minikube cwmc-role- && DEBUG= kubectl uncordon minikube')
    assert ret == 0, out
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl label node minikube cwmc-cleaner-cordon-')
    assert ret == 0, out
    assert list(deployments_manager.iterate_cluster_nodes()) == [{'is_worker': False, 'name': 'minikube', 'unschedulable': False, 'public_ip': node_ip,
                                                                  'cleaner_cordoned': False}]


def test_node_cleanup_pod():
    deployments_manager = DeploymentsManager()
    ret, out = subprocess.getstatusoutput('DEBUG= kubectl taint node minikube cwmc-role=worker:NoSchedule; DEBUG= kubectl uncordon minikube')
    assert ret == 0, out
    try:
        with deployments_manager.node_cleanup_pod('minikube') as ncp:
            subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- rm -rf /cache/example007--com')
            subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- rm -rf /cache/minio-example007--com')
            subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- rm -rf /cache/nginx-example007--com')
            assert ncp.list_cache_namespaces() == []
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- mkdir -p /cache/minio-example007--com')
            assert ret == 0, out
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- mkdir -p /cache/nginx-example007--com')
            assert ret == 0, out
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- touch /cache/minio-example007--com/test.txt')
            assert ret == 0, out
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- touch /cache/nginx-example007--com/test.txt')
            assert ret == 0, out
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- cat /cache/minio-example007--com/test.txt')
            assert ret == 0, out
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- cat /cache/nginx-example007--com/test.txt')
            assert ret == 0, out
            ncp.clear_cache_namespace('example007--com')
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- cat /cache/minio-example007--com/test.txt')
            assert ret == 1, 'file in cache directory was not deleted'
            ret, out = subprocess.getstatusoutput('DEBUG= kubectl -n default exec cwm-worker-operator-node-cleanup -- cat /cache/nginx-example007--com/test.txt')
            assert ret == 1, 'file in cache directory was not deleted'
    finally:
        subprocess.getstatusoutput('DEBUG= kubectl taint node minikube cwmc-role-; DEBUG= kubectl uncordon minikube')


def test_worker_has_pod_on_node():
    deployments_manager = DeploymentsManager()
    assert not deployments_manager.worker_has_pod_on_node('non-existent-namespace', 'non-existent-node')
    assert not deployments_manager.worker_has_pod_on_node('non-existent-namespace', 'minikube')
    assert not deployments_manager.worker_has_pod_on_node('kube-system', 'non-existent-node')
    assert deployments_manager.worker_has_pod_on_node('kube-system', 'minikube')


# TODO: fix this test
@pytest.mark.skip('this takes fails sometimes, need to check why')
def test_dns_healthchecks_records():
    deployments_manager = DeploymentsManager()
    for healthcheck in deployments_manager.iterate_dns_healthchecks():
        deployments_manager.delete_dns_healthcheck(healthcheck['id'])
    assert list(deployments_manager.iterate_dns_healthchecks()) == []
    node1_ip = '1.1.1.1'
    node2_ip = '2.2.2.2'
    node1_healthcheck_id = deployments_manager.set_dns_healthcheck('cwmc-operator-test-node1', node1_ip)
    node2_healthcheck_id = deployments_manager.set_dns_healthcheck('cwmc-operator-test-node2', node2_ip)
    healthchecks = {healthcheck['node_name']: healthcheck for healthcheck in deployments_manager.iterate_dns_healthchecks()}
    assert len(healthchecks) == 2
    node1_healthcheck = healthchecks['cwmc-operator-test-node1']
    node2_healthcheck = healthchecks['cwmc-operator-test-node2']
    assert node1_healthcheck['id'] == node1_healthcheck_id
    assert node2_healthcheck['id'] == node2_healthcheck_id
    assert node1_healthcheck['ip'] == node1_ip
    assert node2_healthcheck['ip'] == node2_ip
    for record in deployments_manager.iterate_dns_records():
        deployments_manager.delete_dns_record(record['id'])
    deployments_manager.set_dns_record('cwmc-operator-test-node1', node1_ip, node1_healthcheck_id)
    deployments_manager.set_dns_record('cwmc-operator-test-node2', node2_ip, node2_healthcheck_id)
    records = {record['node_name']: record for record in deployments_manager.iterate_dns_records()}
    assert len(records) == 2
    node1_record = records['cwmc-operator-test-node1']
    node2_record = records['cwmc-operator-test-node2']
    assert node1_record['ip'] == node1_ip
    assert node2_record['ip'] == node2_ip
    for record in records.values():
        deployments_manager.delete_dns_record(record['id'])
    for healthcheck in healthchecks.values():
        deployments_manager.delete_dns_healthcheck(healthcheck['id'])
    assert list(deployments_manager.iterate_dns_healthchecks()) == []


def test_check_node_nas():
    deployments_manager = DeploymentsManager()
    nodes_statuses = deployments_manager.check_nodes_nas(['minikube'])
    assert set(nodes_statuses.keys()) == {'minikube'}
    statuses = nodes_statuses['minikube']
    assert set(statuses.keys()) == {'1.2.3.4', '5.6.7.8'}
    assert statuses['1.2.3.4']['is_healthy'] is True
    assert statuses['5.6.7.8']['is_healthy'] is True


def test_check_node_nas_multinode_error():
    deployments_manager = DeploymentsManager()

    def overrides_callback(operation, data, default_res):
        if operation == 'nodeSelector':
            return {
                "kubernetes.io/hostname": 'minikube'
            }
        elif operation == 'get_ls_cmd':
            if data['node_name'] == 'minikube3':
                return 'DEBUG= kubectl -n {} exec {} -- sleep 6 && false'.format(data['namespace'], data['pod_name'])
            else:
                return 'DEBUG= kubectl -n {} exec {} -- ls /mnt/nas'.format(data['namespace'], data['pod_name'])
        else:
            return default_res

    nodes_statuses = deployments_manager.check_nodes_nas([
        'minikube',
        'minikube2',
        'minikube3',
        'minikube4',
    ], overrides_callback=overrides_callback)
    assert set(nodes_statuses.keys()) == {'minikube', 'minikube2', 'minikube3', 'minikube4'}
    for node_name, statuses in nodes_statuses.items():
        context = {'node_name': node_name}
        assert set(statuses.keys()) == {'1.2.3.4', '5.6.7.8'}, context
        for ip, ip_statuses in statuses.items():
            context['ip'] = ip
            assert set(ip_statuses.keys()) == {'is_healthy', 'log', 'kubectl_create_success'}, context
            assert ip_statuses['kubectl_create_success'] is True, context
            log_steps = [s['step'] for s in ip_statuses['log']]
            if node_name in ['minikube3']:
                assert ip_statuses['is_healthy'] is False, {**context, 'log': ip_statuses['log']}
                assert log_steps == ['start', 'start kubectl_create', 'end kubectl_create', 'wait_ready_ls', 'wait_ready_failed', 'timeout'], {**context, 'log': ip_statuses['log']}
            else:
                assert ip_statuses['is_healthy'] is True, {**context, 'log': ip_statuses['log']}
                assert log_steps == ['start', 'start kubectl_create', 'end kubectl_create'], {**context, 'log': ip_statuses['log']}


def test_check_node_nas_multinode_timeout():
    deployments_manager = DeploymentsManager()

    def overrides_callback(operation, data, default_res):
        if operation == 'nodeSelector':
            return {
                "kubernetes.io/hostname": 'minikube'
            }
        elif operation == 'get_ls_cmd':
            return 'DEBUG= kubectl -n {} exec {} -- sleep 6 && false'.format(data['namespace'], data['pod_name'])
        else:
            return default_res

    nodes_statuses = deployments_manager.check_nodes_nas([
        'minikube',
        'minikube2',
        'minikube3',
        'minikube4',
    ], overrides_callback=overrides_callback, timeout_seconds_per_node_pod=0.1)
    assert set(nodes_statuses.keys()) == {'minikube', 'minikube2', 'minikube3', 'minikube4'}
    for node_name, statuses in nodes_statuses.items():
        context = {'node_name': node_name}
        assert set(statuses.keys()) == {'1.2.3.4', '5.6.7.8'}, context
        for ip, ip_statuses in statuses.items():
            context['ip'] = ip
            assert set(ip_statuses.keys()) == {'is_healthy', 'log', 'kubectl_create_success'}, context
            assert ip_statuses['kubectl_create_success'] is True, context
            log_steps = [s['step'] for s in ip_statuses['log']]
            assert ip_statuses['is_healthy'] is False, context
            if node_name == 'minikube' and ip == '1.2.3.4':
                assert log_steps == ['start', 'start kubectl_create', 'end kubectl_create', 'wait_ready_ls', 'timeout'], {**context, 'log': ip_statuses['log']}
                assert set(ip_statuses['log'][-2].keys()) == {'dt', 'out', 'ret', 'step'}
                assert ip_statuses['log'][-2]['out'] == ''
                assert ip_statuses['log'][-2]['ret'] == 1
            else:
                assert log_steps == ['start', 'start kubectl_create', 'end kubectl_create', 'timeout'], {**context, 'log': ip_statuses['log']}
            assert ip_statuses['log'][-1]['step'] == 'timeout'
            assert ip_statuses['log'][-1]['timeout_msg'] == 'timeout in node minikube nas_ip 1.2.3.4'
            assert set(ip_statuses['log'][-1].keys()) == {'dt', 'timeout_msg', 'step'}


def test_get_all_namespaces():
    subprocess.call(['kubectl', 'delete', '--wait', 'ns', 'cwm-worker-test123'])
    assert 'cwm-worker-test123' not in DeploymentsManager().get_all_namespaces()
    subprocess.check_call(['kubectl', 'create', 'ns', 'cwm-worker-test123'])
    all_namespaces = DeploymentsManager().get_all_namespaces()
    assert 'cwm-worker-test123' in all_namespaces
    assert 'default' in all_namespaces
    assert 'kube-system' in all_namespaces
    subprocess.check_call(['kubectl', 'delete', '--wait', 'ns', 'cwm-worker-test123'])
