import os
import json
import subprocess


def build_operator_docker_for_minikube():
    print('building docker image for minikube')
    returncode = subprocess.call("""
        eval $(minikube -p minikube docker-env) &&\
        docker pull ghcr.io/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest &&\
        docker build --cache-from ghcr.io/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest \
                     -t ghcr.io/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest .
    """, shell=True)
    assert returncode == 0


def get_volume_config_ssl_keys(name):
    key_filename = 'tests/mocks/{}.key'.format(name)
    pem_filename = 'tests/mocks/{}.pem'.format(name)
    if not os.path.exists(key_filename) or not os.path.exists(pem_filename):
        key_filename = 'tests/mocks/example002.com.key'
        pem_filename = 'tests/mocks/example002.com.pem'
    with open(key_filename) as key_f:
        with open(pem_filename) as pem_f:
            return {'certificate_key': key_f.read().split(), 'certificate_pem': pem_f.read().split()}


def get_volume_config_dict(worker_id='worker1', hostname='example002.com', with_ssl=False, additional_hostnames=None, additional_volume_config=None):
    if not additional_hostnames:
        additional_hostnames = []
    if not additional_volume_config:
        additional_volume_config = {}
    if with_ssl is False:
        hostname_ssl_keys = {}
    elif with_ssl is True:
        hostname_ssl_keys = get_volume_config_ssl_keys(hostname)
    else:
        hostname_ssl_keys = with_ssl
    minio_extra_configs = additional_volume_config.pop('minio_extra_configs', {})
    return {
        'type': 'instance',
        'instanceId': worker_id,
        'minio_extra_configs': {
            'hostnames': [
                {'hostname': hostname, **hostname_ssl_keys},
                *additional_hostnames
            ],
            **minio_extra_configs
        },
        **additional_volume_config
    }


def get_volume_config_json(**kwargs):
    return json.dumps(get_volume_config_dict(**kwargs))


def set_volume_config_key(domains_config, worker_id='worker1', **kwargs):
    domains_config.keys.volume_config.set(worker_id, get_volume_config_json(worker_id=worker_id, **kwargs))
