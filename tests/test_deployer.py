import json

from cwm_worker_operator import deployer
from cwm_worker_operator import common


def assert_domain_deployer_metrics(deployer_metrics, observation):
    assert len(deployer_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in deployer_metrics.observations]), deployer_metrics.observations


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
    worker_id, hostname, namespace_name = domains_config._set_mock_volume_config()
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
    assert deployments_manager.calls[0][0] == 'init'
    assert deployments_manager.calls[0][1][0]['cwm-worker-deployment']['namespace'] == namespace_name
    assert deployments_manager.calls[1][0] == 'deploy'
    assert deployments_manager.calls[1][1][0]['cwm-worker-deployment']['namespace'] == namespace_name
