import os
import time
import datetime
import subprocess

from cwm_worker_operator import domains_config


def test_k8s():
    print('deleting operator')
    subprocess.getstatusoutput('helm delete cwm-worker-operator')
    start_time = datetime.datetime.now()
    while True:
        returncode, _ = subprocess.getstatusoutput('kubectl get deployment cwm-worker-operator cwm-worker-operator-redis')
        if returncode == 1:
            break
        if (datetime.datetime.now() - start_time).total_seconds() > 30:
            raise Exception('waited too long for operator to be deleted')
        time.sleep(1)
    print('deploying k8s')
    returncode, _ = subprocess.getstatusoutput('kubectl get secret github')
    if returncode != 0:
        returncode, output = subprocess.getstatusoutput("""echo '{"auths":{"docker.pkg.github.com":{"auth":"'"$(echo -n "${PACKAGES_READER_GITHUB_USER}:${PACKAGES_READER_GITHUB_TOKEN}" | base64 -w0)"'"}}}' | kubectl create secret generic github --type=kubernetes.io/dockerconfigjson --from-file=.dockerconfigjson=/dev/stdin""")
        assert returncode == 0, output
    helmargs = "--set cwm_api_url={CWM_API_URL},packages_reader_github_user={PACKAGES_READER_GITHUB_USER},packages_reader_github_token={PACKAGES_READER_GITHUB_TOKEN}".format(
        CWM_API_URL=os.environ['CWM_API_URL'],
        PACKAGES_READER_GITHUB_USER=os.environ['PACKAGES_READER_GITHUB_USER'],
        PACKAGES_READER_GITHUB_TOKEN=os.environ['PACKAGES_READER_GITHUB_TOKEN'],
    )
    returncode, output = subprocess.getstatusoutput(
        'helm upgrade --install cwm-worker-operator ./helm {}'.format(helmargs))
    assert returncode == 0, output
    domain_name = 'example007.com'
    print('deleting existing namespace')
    subprocess.getstatusoutput('kubectl delete ns {}'.format(domain_name.replace('.', '--')))
    start_time = datetime.datetime.now()
    while True:
        returncode, output = subprocess.getstatusoutput('kubectl get ns {}'.format(domain_name.replace('.', '--')))
        if returncode == 1:
            break
        if (datetime.datetime.now() - start_time).total_seconds() > 60:
            raise Exception("Waiting too long for existing namespace to be deleted")
        time.sleep(1)
    print('deploying')
    returncode, output = subprocess.getstatusoutput('kubectl get ns {}'.format(domain_name.replace('.', '--')))
    assert returncode == 1, output
    start_time = datetime.datetime.now()
    while True:
        returncode, output = subprocess.getstatusoutput('DEBUG= kubectl exec deployment/cwm-worker-operator-redis -- redis-cli '
                                                        'set {}:{} ""'.format(domains_config.REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name))
        if returncode == 0:
            break
        if (datetime.datetime.now() - start_time).total_seconds() > 60:
            raise Exception("Waiting too long for setting redis key")
        time.sleep(1)
    while True:
        returncode, output = subprocess.getstatusoutput('kubectl -n {} get pods | grep minio- | grep Running'.format(domain_name.replace('.', '--')))
        if returncode == 0:
            break
        if (datetime.datetime.now() - start_time).total_seconds() > 120:
            raise Exception("Waiting too long for worker")
        time.sleep(1)
    returncode, output = subprocess.getstatusoutput(
        'DEBUG= kubectl exec deployment/cwm-worker-operator-redis -- redis-cli '
        '--raw exists {}'.format(domains_config.REDIS_KEY_WORKER_AVAILABLE.format(domain_name)))
    assert returncode == 0 and output == '1'
