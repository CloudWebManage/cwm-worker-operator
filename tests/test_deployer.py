from cwm_worker_operator import deployer
from cwm_worker_operator import common

from .common import get_volume_config_ssl_keys


def assert_domain_deployer_metrics(deployer_metrics, observation):
    assert len(deployer_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in deployer_metrics.observations]), deployer_metrics.observations


def assert_deployment_success(worker_id, hostname, namespace_name, domains_config, deployer_metrics, deployments_manager, expected_additional_hostnames):
    domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    waiting_for_deployment_key = domains_config.keys.worker_waiting_for_deployment_complete._(worker_id)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, ready_for_deployment_key]) == {
        ready_for_deployment_key: '',
        waiting_for_deployment_key: '',
        volume_config_key: ''
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
    assert deployment_config['minio']['MINIO_GATEWAY_DEPLOYMENT_ID'] == worker_id
    assert len(deployment_config['minio']['nginx']['hostnames']) == len(expected_additional_hostnames) + 1
    assert deployment_config['minio']['domain_name'] == hostname
    assert deployment_config['minio']['nginx']['hostnames'][0]['name'] == hostname
    for i, expected_hostname in enumerate(expected_additional_hostnames.keys()):
        assert deployment_config['minio']['nginx']['hostnames'][i+1]['name'] == expected_hostname
        if expected_additional_hostnames[expected_hostname]['ssl']:
            assert set(deployment_config['minio']['nginx']['hostnames'][i+1].keys()) == {'name', 'id', 'key', 'pem'}
        else:
            assert set(deployment_config['minio']['nginx']['hostnames'][i+1].keys()) == {'name', 'id'}
    return deployment_config


def test_invalid_volume_config(domains_config, deployer_metrics, deployments_manager):
    worker_id = 'invalid.volume.config'
    domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    domains_config.keys.volume_config.set(worker_id, '{}')
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    ready_for_deployment_key = domains_config.keys.worker_ready_for_deployment._(worker_id)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key, ready_for_deployment_key]) == {
        ready_for_deployment_key: '',
        volume_config_key: ''
    }
    assert [','.join(o['labels']) for o in deployer_metrics.observations] == [',success_cache', ',failed_to_get_volume_config']
    assert len(deployments_manager.calls) == 0


def test_deployment_failed(domains_config, deployer_metrics, deployments_manager):
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
    domains_config.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))
    deployments_manager.deploy_raise_exception = True
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    volume_config_key = domains_config.keys.volume_config._(worker_id)
    hostname_error_key = domains_config.keys.hostname_error._(hostname)
    assert domains_config._get_all_redis_pools_values(blank_keys=[volume_config_key]) == {
        hostname_error_key: 'FAILED_TO_DEPLOY',
        volume_config_key: ''
    }
    assert [','.join(o['labels']) for o in deployer_metrics.observations] == [',success_cache', ',failed']
    assert len(deployments_manager.calls) == 2
    assert deployments_manager.calls[0][0] == 'init'
    assert deployments_manager.calls[0][1][0]['cwm-worker-deployment']['namespace'] == namespace_name
    assert deployments_manager.calls[1][0] == 'deploy'
    assert deployments_manager.calls[1][1][0]['cwm-worker-deployment']['namespace'] == namespace_name


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
