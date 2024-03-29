import os
import time
import pytz
import datetime
import subprocess

from cwm_worker_operator.common import get_namespace_name_from_worker_id
from cwm_worker_operator.config import DUMMY_TEST_HOSTNAME, DUMMY_TEST_WORKER_ID

from .common import build_operator_docker_for_minikube


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


def test_k8s(domains_config):
    worker_id = DUMMY_TEST_WORKER_ID
    namespace_name = get_namespace_name_from_worker_id(worker_id)
    hostname = DUMMY_TEST_HOSTNAME
    try:
        print('deleting operator')
        subprocess.getstatusoutput('helm delete cwm-worker-operator --wait')
        build_operator_docker_for_minikube()
        print('deploying k8s')
        helmargs = "--set " \
                   "cwm_api_url={CWM_API_URL}," \
                   "cwm_api_key={CWM_API_KEY}," \
                   "cwm_api_secret={CWM_API_SECRET}," \
                   "operator.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS=240," \
                   "operator.daemons={daemons_helm_list}".format(
            CWM_API_URL=os.environ['CWM_API_URL'],
            CWM_API_KEY=os.environ['CWM_API_KEY'],
            CWM_API_SECRET=os.environ['CWM_API_SECRET'],
            daemons_helm_list='{initializer,deployer,waiter,updater,deleter,metrics-updater}',
        )
        cmd = 'helm upgrade --install cwm-worker-operator ./helm {}'.format(helmargs)
        print(cmd)
        returncode, output = subprocess.getstatusoutput(cmd)
        assert returncode == 0, output
        print('deleting existing namespace')
        subprocess.getstatusoutput('kubectl delete ns {}'.format(namespace_name))
        wait_for_cmd('kubectl get ns {}'.format(namespace_name), 1, 60, "Waiting too long for existing namespace to be deleted")
        print('deploying')
        returncode, output = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
        assert returncode == 1, output
        wait_for_cmd(
            'DEBUG= kubectl exec deployment/cwm-worker-operator-redis-{} -- redis-cli set {} ""'.format(
                domains_config.keys.hostname_initialize.redis_pool_name,
                domains_config.keys.hostname_initialize._(hostname)
            ), 0, 60, "Waited too long for setting redis key"
        )
        wait_for_cmd('kubectl -n {} get pods | grep minio-server | grep Running'.format(namespace_name), 0, 240, "Waited too long for worker")
        wait_for_cmd(
            'DEBUG= kubectl exec deployment/cwm-worker-operator-redis-{} -- redis-cli --raw exists {}'.format(
                domains_config.keys.hostname_available.redis_pool_name,
                domains_config.keys.hostname_available._(hostname)
            ), 0, 240, "Waited too long for redis domain availabile", expected_output='1'
        )
    except Exception:
        for cmd in ['kubectl get ns',
                    'kubectl get pods',
                    'kubectl logs deployment/cwm-worker-operator-redis-internal -c redis',
                    'kubectl logs deployment/cwm-worker-operator-initializer -c initializer',
                    'kubectl logs deployment/cwm-worker-operator-deployer -c deployer',
                    'kubectl logs deployment/cwm-worker-operator-waiter -c waiter',
                    'kubectl -n {} get pods'.format(namespace_name),
                    'kubectl -n {} describe pod minio-server'.format(namespace_name),
                    'kubectl -n {} logs deployment/minio-server'.format(namespace_name),
                    'kubectl -n {} describe pod minio-nginx'.format(namespace_name),
                    'kubectl -n {} logs deployment/minio-nginx'.format(namespace_name),
                    'kubectl -n {} describe pod minio-logger'.format(namespace_name),
                    'kubectl -n {} logs deployment/minio-logger'.format(namespace_name),
                    ]:
            print('-- {}'.format(cmd))
            subprocess.call(cmd, shell=True)
        raise
