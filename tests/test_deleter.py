from cwm_worker_operator import deleter


def test_delete(domains_config, deployments_manager):
    domain_name = 'domain.to.delete'
    deleter.delete(domain_name, domains_config=domains_config, deployments_manager=deployments_manager)
    assert domains_config.domain_deleted_worker_keys.get(domain_name) == {}
    assert len(deployments_manager.calls) == 1


def test_deleter_daemon(domains_config, deployments_manager, deleter_metrics):
    domains_config.domains_to_delete += ['domain1.com', 'domain2.com']
    deleter.run_single_iteration(domains_config, deleter_metrics, deployments_manager)
    assert [o['labels'][1] for o in deleter_metrics.observations] == ['success', 'success']
    assert [c[0] + '-' + c[1][0] for c in deployments_manager.calls] == ['delete-domain1--com', 'delete-domain2--com']
