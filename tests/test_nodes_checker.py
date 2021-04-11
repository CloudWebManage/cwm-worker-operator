from cwm_worker_operator import nodes_checker


def test_no_cluster_nodes(domains_config, deployments_manager):
    # no cluster nodes - no actions performed
    nodes_checker.run_single_iteration(domains_config, deployments_manager)
    assert deployments_manager.calls == []
    with domains_config.get_ingress_redis() as r:
        assert len(r.keys("node:healthy:*")) == 0


def test_add_del_some_nodes(domains_config, deployments_manager):
    # 2 healthy nodes, 2 unhealthy nodes, no existing dns records/healthchecks -
    # deletes redis key, dns record, healthchecks for unhealthy nodes
    # adds dns records + healthchecks + redis key
    deployments_manager.cluster_nodes = [
        {'name': 'invalid-node-1', 'is_worker': False, 'unschedulable': False, 'public_ip': '1.1.1.1'},
        {'name': 'invalid-node-2', 'is_worker': False, 'unschedulable': True, 'public_ip': '0.0.0.0'},
        {'name': 'valid-node-3', 'is_worker': True, 'unschedulable': True, 'public_ip': '4.3.2.1'},
        {'name': 'valid-node-4', 'is_worker': True, 'unschedulable': False, 'public_ip': '1.2.3.4'},
    ]
    with domains_config.get_ingress_redis() as r:
        r.set("node_healthy:invalid-node-1", "")
    deployments_manager.dns_healthchecks = [
        {'id': 'existing-healthcheck1', 'node_name': 'invalid-node-1', 'ip': '1.1.1.1'},
        {'id': 'existing-healthcheck2', 'node_name': 'irelevant-node-5', 'ip': '5.5.5.5'}
    ]
    deployments_manager.dns_records = [
        {'id': 'existing-record1', 'node_name': 'invalid-node-2', 'ip': '0.0.0.0'},
        {'id': 'existing-record2', 'node_name': 'irelevant-node-5', 'ip': '5.5.5.5'}
    ]
    nodes_checker.run_single_iteration(domains_config, deployments_manager)
    assert deployments_manager.calls == [
        ('set_dns_healthcheck', ['valid-node-3', '4.3.2.1']),
        ('set_dns_record', ['valid-node-3', '4.3.2.1', 'created-healthcheck-1']),
        ('set_dns_healthcheck', ['valid-node-4', '1.2.3.4']),
        ('set_dns_record', ['valid-node-4', '1.2.3.4', 'created-healthcheck-2']),
        ('delete_dns_record', ['existing-record1']),
        ('delete_dns_record', ['existing-record2']),
        ('delete_dns_healthcheck', ['existing-healthcheck1']),
        ('delete_dns_healthcheck', ['existing-healthcheck2'])
    ]
    with domains_config.get_ingress_redis() as r:
        assert len(r.keys("node:healthy:*")) == 2
        assert r.exists("node:healthy:valid-node-3")
        assert r.exists("node:healthy:valid-node-4")


def test_update_node_ip(domains_config, deployments_manager):
    deployments_manager.cluster_nodes = [
        {'name': 'node1', 'is_worker': True, 'unschedulable': False, 'public_ip': '1.1.1.1'},
        {'name': 'node2', 'is_worker': True, 'unschedulable': True, 'public_ip': '2.2.2.2'},
        {'name': 'node3', 'is_worker': True, 'unschedulable': True, 'public_ip': '3.3.3.3'},
    ]
    deployments_manager.dns_healthchecks = [
        {'id': 'existing-healthcheck1', 'node_name': 'node1', 'ip': '1.1.11.11'},
        {'id': 'existing-healthcheck2', 'node_name': 'node2', 'ip': '2.2.2.2'},
        {'id': 'existing-healthcheck3', 'node_name': 'node3', 'ip': '1.1.1.1'},
    ]
    deployments_manager.dns_records = [
        {'id': 'existing-record1', 'node_name': 'node1', 'ip': '111.111.111.111'},
        {'id': 'existing-record2', 'node_name': 'node2', 'ip': '22.22.22.22'},
        {'id': 'existing-record3', 'node_name': 'node3', 'ip': '3.3.3.3'},
    ]
    nodes_checker.run_single_iteration(domains_config, deployments_manager)
    assert deployments_manager.calls == [
        ('delete_dns_healthcheck', ['existing-healthcheck1']),
        ('delete_dns_healthcheck', ['existing-healthcheck3']),
        ('delete_dns_record', ['existing-record1']),
        ('delete_dns_record', ['existing-record2']),
        ('delete_dns_record', ['existing-record3']),
        ('set_dns_healthcheck', ['node1', '1.1.1.1']),
        ('set_dns_record', ['node1', '1.1.1.1', 'created-healthcheck-1']),
        ('set_dns_record', ['node2', '2.2.2.2', 'existing-healthcheck2']),
        ('set_dns_healthcheck', ['node3', '3.3.3.3']),
        ('set_dns_record', ['node3', '3.3.3.3', 'created-healthcheck-2'])
    ]