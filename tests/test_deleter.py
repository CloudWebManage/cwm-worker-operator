from cwm_worker_operator import deleter


def test_delete(domains_config, deployments_manager):
    domain_name = 'domain.to.delete'
    deleter.delete(domain_name, domains_config=domains_config, deployments_manager=deployments_manager)
    assert domains_config.domain_deleted_worker_keys.get(domain_name) == {}
    assert len(deployments_manager.calls) == 1
