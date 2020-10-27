import datetime

from cwm_worker_operator import waiter, config


def assert_domain_waiter_metrics(waiter_metrics, observation):
    assert len(waiter_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in waiter_metrics.observations]), waiter_metrics.observations


def test_invalid_volume_config(domains_config, waiter_metrics, deployments_manager):
    domain_name = 'invalid.volume.config'
    domains_config.worker_domains_waiting_for_deployment_complete.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, None
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    assert not domains_config.domain_worker_available_hostname.get(domain_name)
    assert_domain_waiter_metrics(waiter_metrics, 'failed_to_get_volume_config')
    assert len(deployments_manager.calls) == 0


def test_deployment_not_ready(domains_config, waiter_metrics, deployments_manager):
    domain_name = 'deployment.not.ready'
    namespace_name = domain_name.replace('.', '--')
    domains_config.worker_domains_waiting_for_deployment_complete.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, namespace_name
    deployments_manager.namespace_deployment_type_is_ready['{}-minio'.format(namespace_name)] = False
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    assert not domains_config.domain_worker_available_hostname.get(domain_name)
    assert len(waiter_metrics.observations) == 0
    assert len(deployments_manager.calls) == 1


def test_deployment_not_ready_timeout(domains_config, waiter_metrics, deployments_manager):
    domain_name = 'deployment.timeout'
    namespace_name = domain_name.replace('.', '--')
    domains_config.worker_domains_waiting_for_deployment_complete.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, namespace_name
    deployments_manager.namespace_deployment_type_is_ready['{}-minio'.format(namespace_name)] = False
    domains_config.domain_ready_for_deployment_start_time[domain_name] = datetime.datetime.now() - datetime.timedelta(days=1)
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    assert not domains_config.domain_worker_available_hostname.get(domain_name)
    assert_domain_waiter_metrics(waiter_metrics, 'timeout')
    assert len(deployments_manager.calls) == 1


def test_deployment_ready(domains_config, waiter_metrics, deployments_manager):
    config.WAITER_VERIFY_WORKER_ACCESS = True
    domain_name = 'deployment.timeout'
    namespace_name = domain_name.replace('.', '--')
    internal_hostname = 'internal.hostname'
    domains_config.worker_domains_waiting_for_deployment_complete.append(domain_name)
    domains_config.domain_volume_config_namespace[domain_name] = {}, namespace_name
    deployments_manager.namespace_deployment_type_is_ready['{}-minio'.format(namespace_name)] = True
    deployments_manager.namespace_deployment_type_hostname['{}-minio'.format(namespace_name)] = internal_hostname
    deployments_manager.hostname_verify_worker_access[internal_hostname] = True
    waiter.run_single_iteration(domains_config, waiter_metrics, deployments_manager)
    assert domains_config.domain_worker_available_hostname.get(domain_name) == internal_hostname
    assert_domain_waiter_metrics(waiter_metrics, 'success')
    assert len(deployments_manager.calls) == 4
