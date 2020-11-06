import os
import time
import shutil
import pytest
import datetime
import subprocess

from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import config


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
    prompf = subprocess.Popen('exec kubectl port-forward service/prometheus-kube-prometheus-prometheus 9090', shell=True)
    try:
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
            'minio': {
                'createPullSecret': config.PULL_SECRET,
                'service': {
                    'enabled': False
                }
            },
            'extraObjects': []
        }
        deployments_manager.init(deployment_config)
        returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
        assert returncode == 0
        deployments_manager.init(deployment_config)
        returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
        assert returncode == 0
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get service minio'.format(namespace_name))
        assert returncode == 1
        deployments_manager.deploy_external_service(deployment_config)
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get service minio'.format(namespace_name))
        assert returncode == 0
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get service test-extra-object'.format(namespace_name))
        assert returncode == 1
        deployments_manager.deploy_extra_objects(deployment_config, [{
            'apiVersion': 'v1',
            'kind': 'Service',
            'name': 'test-extra-object',
            'spec': 'ports:\n- name: "8080"\n  port: 8080\n  TargetPort: 8080\nselector:\n  app: minio'}])
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get service test-extra-object'.format(namespace_name))
        assert returncode == 0
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio'.format(namespace_name))
        assert returncode == 1
        print("Deploying...")
        deployments_manager.deploy(deployment_config, with_init=False, atomic_timeout_string='2m')
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio'.format(namespace_name))
        assert returncode == 0
        start_time = datetime.datetime.now()
        while not deployments_manager.is_ready(namespace_name, 'minio'):
            time.sleep(1)
            if (datetime.datetime.now() - start_time).total_seconds() > 30:
                raise Exception("Waited too long for deployment to be ready")
        ingress_hostname = deployments_manager.get_hostname(namespace_name, 'minio')
        assert ingress_hostname == 'minio.{}.svc.cluster.local'.format(namespace_name)
        all_releases = {r['namespace']: r for r in deployments_manager.iterate_all_releases()}
        assert namespace_name in all_releases
        worker_metrics = deployments_manager.get_worker_metrics(namespace_name)
        assert set(worker_metrics.keys()) == {
            'network_receive_bytes_total_last_10m',
            'network_receive_bytes_total_last_12h',
            'network_receive_bytes_total_last_1h',
            'network_receive_bytes_total_last_24h',
            'network_receive_bytes_total_last_30m',
            'network_receive_bytes_total_last_3h',
            'network_receive_bytes_total_last_48h',
            'network_receive_bytes_total_last_5m',
            'network_receive_bytes_total_last_6h',
            'network_receive_bytes_total_last_72h',
            'network_receive_bytes_total_last_96h'
        }
        deployments_manager.delete(namespace_name, 'minio', delete_helm=False, delete_namespace=False)
        returncode, _ = subprocess.getstatusoutput('kubectl -n {} get deployment minio'.format(namespace_name))
        assert returncode == 1
        returncode, _ = subprocess.getstatusoutput('helm -n {0} get all minio-{0}'.format(namespace_name))
        assert returncode == 0
        deployments_manager.delete(namespace_name, 'minio', delete_helm=True, delete_namespace=False)
        returncode, _ = subprocess.getstatusoutput('helm -n {0} get all minio-{0}'.format(namespace_name))
        assert returncode == 1
        deployments_manager.delete(namespace_name, 'minio', delete_helm=True, delete_namespace=True)
        start_time = datetime.datetime.now()
        while True:
            returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
            if returncode == 1:
                break
            if (datetime.datetime.now() - start_time).total_seconds() > 60:
                raise Exception("Waited too long for namespace to be deleted")
    finally:
        prompf.terminate()


@pytest.mark.filterwarnings("ignore:Unverified HTTPS request.*")
def test_verify_worker_access():
    subprocess.getstatusoutput('docker rm -f mocknginx')
    returncode, _ = subprocess.getstatusoutput('docker build -t mocknginx tests/mocks/nginx && docker run -p 8080:80 -p 8443:443 -d --name mocknginx mocknginx')
    assert returncode == 0
    time.sleep(5)
    assert DeploymentsManager().verify_worker_access('localhost', {})