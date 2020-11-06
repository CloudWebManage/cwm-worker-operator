from cwm_worker_operator import initializer
from cwm_worker_operator import config


def assert_domain_initializer_configs(domains_config, domain_name, ready_for_deployment=False, error=None, error_attempt_number=None):
    assert domains_config.domain_worker_ready_for_deployment.get(domain_name, False) == ready_for_deployment
    assert domains_config.domain_worker_error.get(domain_name) == error
    assert domains_config.domain_worker_error_attempt_number.get(domain_name) == error_attempt_number


def assert_domain_initializer_metrics(initializer_metrics, observation):
    assert len(initializer_metrics.observations) > 0
    assert all([','.join(o['labels']) == ',{}'.format(observation) for o in initializer_metrics.observations])


def test_invalid_volume_config(domains_config, initializer_metrics):
    domain_name = 'invalid-config-domain.com'
    domains_config.worker_domains_waiting_for_initlization.append(domain_name)
    for i in range(1, config.WORKER_ERROR_MAX_ATTEMPTS):
        initializer.run_single_iteration(domains_config, initializer_metrics)
        assert_domain_initializer_configs(domains_config, domain_name, error_attempt_number=i)
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert_domain_initializer_configs(domains_config, domain_name,
                                      error=domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG,
                                      error_attempt_number=config.WORKER_ERROR_MAX_ATTEMPTS)
    assert_domain_initializer_metrics(initializer_metrics, 'failed_to_get_volume_config')
    assert domains_config.get_cwm_api_volume_config_calls[domain_name] == [{'force_update': False} for i in range(5)]


def test_invalid_volume_zone(domains_config, initializer_metrics):
    domain_name = 'invalid-zone.com'
    domains_config.worker_domains_waiting_for_initlization.append(domain_name)
    domains_config.domain_cwm_api_volume_config[domain_name] = {'hostname': domain_name, 'zone': 'INVALID'}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert_domain_initializer_configs(domains_config, domain_name, error=domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE)
    assert_domain_initializer_metrics(initializer_metrics, 'invalid_volume_zone')
    assert domains_config.get_cwm_api_volume_config_calls[domain_name] == [{'force_update': False}]


def test_valid_domain(domains_config, initializer_metrics):
    domain_name = 'valid-domain.com'
    domains_config.worker_domains_waiting_for_initlization.append(domain_name)
    domains_config.domain_cwm_api_volume_config[domain_name] = {'hostname': domain_name, 'zone': config.CWM_ZONE}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert_domain_initializer_configs(domains_config, domain_name, ready_for_deployment=True)
    assert_domain_initializer_metrics(initializer_metrics, 'initialized')
    assert domains_config.get_cwm_api_volume_config_calls[domain_name] == [{'force_update': False}]


def test_force_update_domain(domains_config, initializer_metrics):
    domain_name = 'force-update.domain'
    domains_config.worker_domains_force_update.append(domain_name)
    domains_config.domain_cwm_api_volume_config[domain_name] = {'hostname': domain_name, 'zone': config.CWM_ZONE}
    initializer.run_single_iteration(domains_config, initializer_metrics)
    assert_domain_initializer_configs(domains_config, domain_name, ready_for_deployment=True)
    assert_domain_initializer_metrics(initializer_metrics, 'initialized')
    assert domains_config.get_cwm_api_volume_config_calls[domain_name] == [{'force_update': True}]
