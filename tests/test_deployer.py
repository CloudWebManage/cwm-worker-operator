from cwm_worker_operator import deployer


def assert_domain_deployer_metrics(deployer_metrics, observation):
    assert len(deployer_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in deployer_metrics.observations]), deployer_metrics.observations


def test_invalid_volume_config(domains_config, deployer_metrics, deployments_manager):
    domain_name = 'invalid.volume.config'
    domains_config.worker_domains_ready_for_deployment.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, None
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    assert not domains_config.domain_worker_waiting_for_deployment.get(domain_name)
    assert_domain_deployer_metrics(deployer_metrics, 'failed_to_get_volume_config')
    assert len(deployments_manager.calls) == 0


def test_deployment_failed(domains_config, deployer_metrics, deployments_manager):
    domain_name = 'invalid.deployment'
    domains_config.worker_domains_ready_for_deployment.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, 'invalid--deployment'
    deployments_manager.deploy_raise_exception = True
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    assert not domains_config.domain_worker_waiting_for_deployment.get(domain_name)
    assert_domain_deployer_metrics(deployer_metrics, 'failed')
    assert len(deployments_manager.calls) == 2


def test_deployment_success(domains_config, deployer_metrics, deployments_manager):
    domain_name = 'valid.deployment'
    domains_config.worker_domains_ready_for_deployment.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, 'valid--deployment'
    deployer.run_single_iteration(domains_config, deployer_metrics, deployments_manager)
    assert domains_config.domain_worker_waiting_for_deployment.get(domain_name)
    assert_domain_deployer_metrics(deployer_metrics, 'success')
    assert len(deployments_manager.calls) == 2