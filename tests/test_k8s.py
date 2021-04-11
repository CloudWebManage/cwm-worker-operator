import os
import time
import pytz
import datetime
import subprocess

from cwm_worker_operator import domains_config

from .common import build_operator_docker_for_minikube, set_github_secret


def wait_for_cmd(cmd, expected_returncode, ttl_seconds, error_msg, expected_output=None):
    start_time = datetime.datetime.now(pytz.UTC)
    while True:
        returncode, output = subprocess.getstatusoutput(cmd)
        if returncode == expected_returncode and (expected_output is None or expected_output == output):
            break
        if (datetime.datetime.now(pytz.UTC) - start_time).total_seconds() > ttl_seconds:
            print(output)
            raise Exception(error_msg)
        time.sleep(1)


def test_k8s():
    try:
        print('deleting operator')
        subprocess.getstatusoutput('helm delete cwm-worker-operator')
        wait_for_cmd('kubectl get deployment cwm-worker-operator cwm-worker-operator-redis-ingress cwm-worker-operator-redis-metrics',
                     1, 30, 'waited too long for operator to be deleted')
        build_operator_docker_for_minikube()
        set_github_secret()
        print('deploying k8s')
        helmargs = "--set " \
                   "cwm_api_url={CWM_API_URL}," \
                   "packages_reader_github_user={PACKAGES_READER_GITHUB_USER}," \
                   "packages_reader_github_token={PACKAGES_READER_GITHUB_TOKEN}," \
                   "operator.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS=120," \
                   "operator.daemons={daemons_helm_list}".format(
            CWM_API_URL=os.environ['CWM_API_URL'],
            PACKAGES_READER_GITHUB_USER=os.environ['PACKAGES_READER_GITHUB_USER'],
            PACKAGES_READER_GITHUB_TOKEN=os.environ['PACKAGES_READER_GITHUB_TOKEN'],
            daemons_helm_list='{initializer,deployer,waiter,updater,deleter,metrics-updater}',
        )
        returncode, output = subprocess.getstatusoutput(
            'helm upgrade --install cwm-worker-operator ./helm {}'.format(helmargs))
        assert returncode == 0, output
        domain_name = 'example007.com'
        print('deleting existing namespace')
        subprocess.getstatusoutput('kubectl delete ns {}'.format(domain_name.replace('.', '--')))
        wait_for_cmd('kubectl get ns {}'.format(domain_name.replace('.', '--')),
                     1, 60, "Waiting too long for existing namespace to be deleted")
        print('deploying')
        returncode, output = subprocess.getstatusoutput('kubectl get ns {}'.format(domain_name.replace('.', '--')))
        assert returncode == 1, output
        wait_for_cmd('DEBUG= kubectl exec deployment/cwm-worker-operator-redis-ingress -- redis-cli '
                     'set {}:{} ""'.format(domains_config.REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name),
                     0, 60, "Waited too long for setting redis key")
        wait_for_cmd('kubectl -n {} get pods | grep minio- | grep Running'.format(domain_name.replace('.', '--')),
                     0, 120, "Waited too long for worker")
        wait_for_cmd('DEBUG= kubectl exec deployment/cwm-worker-operator-redis-ingress -- redis-cli '
                     '--raw exists {}'.format(domains_config.REDIS_KEY_WORKER_AVAILABLE.format(domain_name)),
                     0, 120, "Waited too long for redis domain availabile", expected_output='1')
    except Exception:
        for cmd in ['kubectl get ns',
                    'kubectl get pods',
                    'kubectl logs deployment/cwm-worker-operator -c redis',
                    'kubectl logs deployment/cwm-worker-operator -c initializer',
                    'kubectl logs deployment/cwm-worker-operator -c deployer',
                    'kubectl logs deployment/cwm-worker-operator -c waiter',
                    'kubectl -n example007--com get pods',
                    'kubectl -n example007--com describe pod minio-http',
                    'kubectl -n example007--com logs deployment/minio-http',
                    'kubectl -n example007--com describe pod minio-https',
                    'kubectl -n example007--com logs deployment/minio-https',
                    'kubectl -n example007--com describe pod minio-logger',
                    'kubectl -n example007--com logs deployment/minio-logger',
                    ]:
            print('-- {}'.format(cmd))
            subprocess.call(cmd, shell=True)
        raise
