import subprocess

from cwm_worker_operator import deployer
from cwm_worker_operator import common
from cwm_worker_operator import config

from .common import get_volume_config_ssl_keys
from .test_domains_config import CERTIFICATE_KEY, CERTIFICATE_PEM, INTERMEDIATE_CERTIFICATES
from cwm_worker_operator import deployment_flow_manager


def assert_domain_deployer_metrics(deployer_metrics, observation):
    assert len(deployer_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in deployer_metrics.observations]), deployer_metrics.observations


def assert_deployment_success(worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager, expected_additional_hostnames):
    domains_config.keys.hostname_initialize.set(hostname, '')
    domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager, is_async=False)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_initialize_key = domains_config.keys.hostname_initialize._(hostname)
    ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    waiting_for_deployment_key = domains_config.keys.worker_waiting_for_deployment_complete._(worker_id)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    hostname_last_deployment_flow_action_key = domains_config.keys.hostname_last_deployment_flow_action._(hostname)
    hostname_last_deployment_flow_time_key = domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    hostname_last_deployment_flow_worker_id_key = domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname)
    additional_hostnames_blank_keys = []
    additional_hostnames_redis_pool_values = {}
    for additional_hostname in expected_additional_hostnames:
        additional_hostnames_blank_keys.append(
            domains_config.keys.hostname_last_deployment_flow_time._(additional_hostname)
        )
        additional_hostnames_redis_pool_values[
            domains_config.keys.hostname_last_deployment_flow_time._(additional_hostname)
        ] = ''
        additional_hostnames_redis_pool_values[
            domains_config.keys.hostname_last_deployment_flow_action._(additional_hostname)
        ] = deployment_flow_manager.DEPLOYER_WORKER_WAITING_FOR_DEPLOYMENT
        additional_hostnames_redis_pool_values[
            domains_config.keys.hostname_last_deployment_flow_worker_id._(additional_hostname)
        ] = worker_id
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key, ready_for_deployment_key,
        last_deployment_flow_time_key, hostname_last_deployment_flow_time_key,
        *additional_hostnames_blank_keys
    ]) == {
        ready_for_deployment_key: '',
        waiting_for_deployment_key: '',
        volume_config_key: '',
        hostname_initialize_key: '',
        last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WORKER_WAITING_FOR_DEPLOYMENT,
        hostname_last_deployment_flow_worker_id_key: worker_id,
        hostname_last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WORKER_WAITING_FOR_DEPLOYMENT,
        hostname_last_deployment_flow_time_key: '',
        **additional_hostnames_redis_pool_values
    }
    assert [','.join(o['labels']) for o in deployer_metrics.observations] == [',success_cache', ',success']
    assert len(deployments_manager.calls) == 2
    init_call, deploy_call = deployments_manager.calls
    assert init_call[0] == 'init'
    assert deploy_call[0] == 'deploy'
    init_params = init_call[1]
    deploy_params = deploy_call[1]
    assert init_params[0]['cwm-worker-deployment']['namespace'] == namespace_name
    assert deploy_params[0]['cwm-worker-deployment']['namespace'] == namespace_name
    deployment_config = deploy_params[0]
    assert deployment_config['minio']['MINIO_GATEWAY_DEPLOYMENT_ID'] == common.get_namespace_name_from_worker_id(worker_id)
    assert len(deployment_config['minio']['nginx']['hostnames']) == len(expected_additional_hostnames) + 1
    assert deployment_config['minio']['domain_name'] == hostname
    assert deployment_config['minio']['nginx']['hostnames'][0]['name'] == hostname
    for i, expected_hostname in enumerate(expected_additional_hostnames.keys()):
        assert deployment_config['minio']['nginx']['hostnames'][i+1]['name'] == expected_hostname
        expected_keys = {'name', 'id'}
        if expected_additional_hostnames[expected_hostname]['ssl']:
            expected_keys.add('fullchain')
            expected_keys.add('chain')
            expected_keys.add('privkey')
        if expected_additional_hostnames[expected_hostname].get('challenge'):
            expected_keys.add('cc_payload')
            expected_keys.add('cc_token')
        assert set(deployment_config['minio']['nginx']['hostnames'][i+1].keys()) == expected_keys
    return deployment_config


def test_invalid_volume_config(domains_config, deployer_metrics, deployments_manager):
    worker_id = 'invalid.volume.config'
    domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    domains_config.keys.volume_config.set(worker_id, '{}')
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager, is_async=False)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, last_deployment_flow_time_key]) == {
        volume_config_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WORKER_ERROR,
        last_deployment_flow_time_key: ''
    }
    assert [','.join(o['labels']) for o in deployer_metrics.observations] == [',success_cache', ',failed_to_get_volume_config']
    assert len(deployments_manager.calls) == 0


def test_deployment_failed(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    domains_config.keys.hostname_initialize.set(hostname, '')
    domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_error_key = domains_config.keys.hostname_error._(hostname)
    hostname_initialize_key = domains_config.keys.hostname_initialize._(hostname)
    deployment_error_attempt_key = domains_config.keys.worker_deployment_error_attempt._(worker_id)
    ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    waiting_for_deployment_key = domains_config.keys.worker_waiting_for_deployment_complete._(worker_id)
    last_deployment_flow_action_key = domains_config.keys.worker_last_deployment_flow_action._(worker_id)
    last_deployment_flow_time_key = domains_config.keys.worker_last_deployment_flow_time._(worker_id)
    hostname_last_deployment_flow_action_key = domains_config.keys.hostname_last_deployment_flow_action._(hostname)
    hostname_last_deployment_flow_time_key = domains_config.keys.hostname_last_deployment_flow_time._(hostname)
    hostname_last_deployment_flow_worker_id_key = domains_config.keys.hostname_last_deployment_flow_worker_id._(hostname)
    # first attempt - will retry
    deployments_manager.deploy_raise_exception = True
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager, is_async=False)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key, ready_for_deployment_key,
        last_deployment_flow_time_key, hostname_last_deployment_flow_time_key
    ]) == {
        # hostname_error_key: 'FAILED_TO_DEPLOY',
        deployment_error_attempt_key: '1',
        ready_for_deployment_key: '',
        waiting_for_deployment_key: 'error',
        volume_config_key: '',
        hostname_initialize_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WAIT_RETRY_DEPLOYMENT,
        last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WAIT_RETRY_DEPLOYMENT,
        hostname_last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_worker_id_key: worker_id
    }
    assert [','.join(o['labels']) for o in deployer_metrics.observations] == [',success_cache', ',failed']
    assert len(deployments_manager.calls) == 2
    assert deployments_manager.calls[0][0] == 'init'
    assert deployments_manager.calls[0][1][0]['cwm-worker-deployment']['namespace'] == namespace_name
    assert deployments_manager.calls[1][0] == 'deploy'
    assert deployments_manager.calls[1][1][0]['cwm-worker-deployment']['namespace'] == namespace_name
    # now it's handled by the waiter, so another call to deployer won't do anything
    deployments_manager.calls = []
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager, is_async=False)
    assert len(deployments_manager.calls) == 0
    # delete waiter key and set attempt number to max, so it won't retry and fail this time
    deployments_manager.calls = []
    domains_config.keys.worker_deployment_error_attempt.set(worker_id, config.DEPLOYER_MAX_ATTEMPT_NUMBERS)
    domains_config.keys.worker_waiting_for_deployment_complete.delete(worker_id)
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager, is_async=False)
    assert len(deployments_manager.calls) == 2
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        volume_config_key,
        last_deployment_flow_time_key, hostname_last_deployment_flow_time_key
    ]) == {
        hostname_error_key: 'FAILED_TO_DEPLOY',
        volume_config_key: '',
        last_deployment_flow_time_key: '',
        last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WORKER_ERROR,
        hostname_last_deployment_flow_action_key: deployment_flow_manager.DEPLOYER_WORKER_ERROR,
        hostname_last_deployment_flow_time_key: '',
        hostname_last_deployment_flow_worker_id_key: worker_id
    }


def test_deployment_success(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl=True, additional_hostnames=[
        {'hostname': 'example001.com'},
        {'hostname': 'example003.com', **get_volume_config_ssl_keys('example003.com')}
    ])
    deployment_config = assert_deployment_success(
        worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager,
        expected_additional_hostnames = {'example001.com': {'ssl': False}, 'example003.com': {'ssl': True}}
    )
    assert 'INSTANCE_TYPE' not in deployment_config['minio']
    assert 'GATEWAY_ARGS' not in deployment_config['minio']
    assert 'AWS_ACCESS_KEY_ID' not in deployment_config['minio']
    assert 'AWS_SECRET_ACCESS_KEY' not in deployment_config['minio']


def test_deployment_gateway_s3(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl=True, additional_hostnames=[
        {'hostname': 'example001.com'},
        {'hostname': 'example003.com', **get_volume_config_ssl_keys('example003.com')}
    ], additional_volume_config={
        'instanceType': 'gateway_s3',
        'gatewayS3Url': 'https://minio-source.example.com',
        'gatewayS3AccessKey': 'username',
        'gatewayS3SecretAccessKey': 'password'
    })
    deployment_config = assert_deployment_success(
        worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager,
        expected_additional_hostnames={'example001.com': {'ssl': False}, 'example003.com': {'ssl': True}}
    )
    assert deployment_config['minio']['INSTANCE_TYPE'] == 'gateway_s3'
    assert deployment_config['minio']['GATEWAY_ARGS'] == 'https://minio-source.example.com'
    assert deployment_config['minio']['AWS_ACCESS_KEY_ID'] == 'username'
    assert deployment_config['minio']['AWS_SECRET_ACCESS_KEY'] == 'password'


def test_deployment_gateway_s3_aws(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl=True, additional_hostnames=[
        {'hostname': 'example001.com'},
        {'hostname': 'example003.com', **get_volume_config_ssl_keys('example003.com')}
    ], additional_volume_config={
        'instanceType': 'gateway_s3',
        'gatewayS3AccessKey': 'username',
        'gatewayS3SecretAccessKey': 'password'
    })
    deployment_config = assert_deployment_success(
        worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager,
        expected_additional_hostnames={'example001.com': {'ssl': False}, 'example003.com': {'ssl': True}}
    )
    assert deployment_config['minio']['INSTANCE_TYPE'] == 'gateway_s3'
    assert 'GATEWAY_ARGS' not in deployment_config['minio']
    assert deployment_config['minio']['AWS_ACCESS_KEY_ID'] == 'username'
    assert deployment_config['minio']['AWS_SECRET_ACCESS_KEY'] == 'password'


def test_deployment_gateway_google(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl=True, additional_hostnames=[
        {'hostname': 'example001.com'},
        {'hostname': 'example003.com', **get_volume_config_ssl_keys('example003.com')}
    ], additional_volume_config={
        'type': 'gateway',
        'provider': 'gcs',
        'credentials': {
            'projectId': 'myproject123',
            'credentialsJson': {"hello": "world"}
        },
    })
    deployment_config = assert_deployment_success(
        worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager,
        expected_additional_hostnames={'example001.com': {'ssl': False}, 'example003.com': {'ssl': True}}
    )
    assert deployment_config['minio']['INSTANCE_TYPE'] == 'gateway_gcs'
    assert deployment_config['minio']['GATEWAY_ARGS'] == 'myproject123'
    assert deployment_config['minio']['GOOGLE_APPLICATION_CREDENTIALS'] == {"hello": "world"}


def test_deployment_challenge(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl=True, additional_hostnames=[
        {'hostname': 'example001.com', 'token': 'aaTOKENbb', 'payload': 'yyPAYLOADzz'},
        {'hostname': 'example003.com', **get_volume_config_ssl_keys('example003.com')}
    ])
    deployment_config = assert_deployment_success(
        worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager,
        expected_additional_hostnames={'example001.com': {'ssl': False, 'challenge': True},
                                       'example003.com': {'ssl': True}}
    )
    hostnames = deployment_config['minio']['nginx']['hostnames']
    assert hostnames[1]['cc_token'] == 'aaTOKENbb'
    assert hostnames[1]['cc_payload'] == 'yyPAYLOADzz'
    assert 'cc_token' not in hostnames[2] and 'cc_payload' not in hostnames[2]
    assert 'cc_token' not in hostnames[0] and 'cc_payload' not in hostnames[0]


def test_deployment_ssl_chain(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(with_ssl={
        'privateKey': CERTIFICATE_KEY,
        'fullChain': [*CERTIFICATE_PEM, *INTERMEDIATE_CERTIFICATES],
        'chain': INTERMEDIATE_CERTIFICATES
    })
    deployment_config = assert_deployment_success(
        worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager,
        expected_additional_hostnames={}
    )
    hostnames = deployment_config['minio']['nginx']['hostnames']
    assert len(hostnames) == 1
    assert set(hostnames[0].keys()) == {'privkey', 'name', 'chain', 'fullchain', 'id'}
    assert hostnames[0]['privkey'] == "\n".join(CERTIFICATE_KEY)
    assert hostnames[0]['fullchain'] == "\n".join([*CERTIFICATE_PEM, *INTERMEDIATE_CERTIFICATES])
    assert hostnames[0]['chain'] == "\n".join(INTERMEDIATE_CERTIFICATES)


def test_deployer_async(domains_config, deployer_metrics, deployments_manager):
    workers = {}
    for i in range(1, 4):
        worker_id = 'worker{}'.format(i)
        hostname = 'worker{}.example.com'.format(i)
        worker_id, hostname, namespace_name = domains_config._set_mock_volume_config(worker_id=worker_id, hostname=hostname)
        workers['worker{}'.format(i)] = {
            'hostname': hostname,
            'worker_id': worker_id,
            'namespace_name': namespace_name
        }
        domains_config.keys.hostname_initialize.set(hostname, '')
        domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    namespace_names = [w['namespace_name'] for w in workers.values()]
    ret, out = subprocess.getstatusoutput('kubectl delete ns {} --wait --timeout 60s'.format(' '.join(namespace_names)))
    if ret != 0:
        print(out)
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    ret, out = subprocess.getstatusoutput('kubectl get ns {}'.format(' '.join(namespace_names)))
    assert ret == 0, out
    ret, out = subprocess.getstatusoutput('kubectl delete ns {} --wait --timeout 60s'.format(' '.join(namespace_names)))
    assert ret == 0, out
