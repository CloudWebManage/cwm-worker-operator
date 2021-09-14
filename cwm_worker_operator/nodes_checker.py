"""
Checks nodes and updates DNS records accordingly

It doesn't actually do any healthchecks itself, it just updates DNS records for
all cluster worker nodes. Each worker node also gets an AWS Route53 healthcheck
which does the actual healthcheck and removes it from DNS if it fails. The
healthchecks check cwm-worker-ingress /healthz path, so if the ingress stops
responding the node is removed from DNS.

In addition to the DNS healthchecks, the cwm-worker-ingress checks redis key
node:healthy, if key is missing the /healthz path returns an error. nodes_checker
updates this redis key to true for all worker nodes and to false for any nodes
which are not currently listed as worker nodes - so nodes which are removed
will instantly stop serving.
"""
from cwm_worker_operator import config
from cwm_worker_operator.daemon import Daemon


def set_node_healthy_keys(domains_config, deployments_manager):
    healthy_node_name_ips = {}
    # set healthy redis key of healthy nodes - so that ingress will report them as healthy
    for node in deployments_manager.iterate_cluster_nodes():
        if node['is_worker']:
            healthy_node_name_ips[node['name']] = node['public_ip']
            domains_config.set_node_healthy(node['name'], True)
    # del healthy redis key for nodes which have a key but are not in list of healthy nodes
    for node_name in domains_config.iterate_healthy_node_names():
        if node_name not in healthy_node_name_ips:
            domains_config.set_node_healthy(node_name, False)
    return healthy_node_name_ips


def update_dns_records(deployments_manager, healthy_node_name_ips):
    dns_healthchecks = {}
    dns_records = {}
    # collect node names of existing dns healthchecks / records
    # delete records which need updating for recreation
    update_required_healthcheck_node_names = set()
    update_required_records_node_names = set()
    for dns_healthcheck in deployments_manager.iterate_dns_healthchecks():
        dns_healthchecks[dns_healthcheck['node_name']] = {'id': dns_healthcheck['id'], 'ip': dns_healthcheck['ip']}
        if dns_healthcheck['node_name'] in healthy_node_name_ips and dns_healthcheck['ip'] != healthy_node_name_ips[
            dns_healthcheck['node_name']]:
            deployments_manager.delete_dns_healthcheck(dns_healthcheck['id'])
            update_required_healthcheck_node_names.add(dns_healthcheck['node_name'])
    for dns_record in deployments_manager.iterate_dns_records():
        dns_records[dns_record['node_name']] = {'id': dns_record['id'], 'ip': dns_record['ip']}
        if dns_record['node_name'] in update_required_healthcheck_node_names or (dns_record['node_name'] in healthy_node_name_ips and dns_record['ip'] != healthy_node_name_ips[dns_record['node_name']]):
            deployments_manager.delete_dns_record(dns_record['id'])
            update_required_records_node_names.add(dns_record['node_name'])
    # set dns healthcheck and record for nodes which are in list of healthy nodes but have a missing healthcheck or record
    for node_name, node_ip in healthy_node_name_ips.items():
        if node_name not in dns_healthchecks or node_name in update_required_healthcheck_node_names:
            healthcheck_id = deployments_manager.set_dns_healthcheck(node_name, node_ip)
        else:
            healthcheck_id = dns_healthchecks[node_name]['id']
        if node_name not in dns_records or node_name in update_required_records_node_names:
            deployments_manager.set_dns_record(node_name, node_ip, healthcheck_id)
    return dns_healthchecks, dns_records


def delete_dns_records(deployments_manager, healthy_node_name_ips, dns_healthchecks, dns_records):
    # delete dns records for nodes which are not in list of healthy nodes
    for node_name, dns_record in dns_records.items():
        if node_name not in healthy_node_name_ips:
            deployments_manager.delete_dns_record(dns_record['id'])
    # delete dns healthcheck for nodes which are not in list of healthy nodes
    for node_name, healthcheck in dns_healthchecks.items():
        if node_name not in healthy_node_name_ips:
            deployments_manager.delete_dns_healthcheck(healthcheck['id'])


def run_single_iteration(domains_config, deployments_manager, **_):
    healthy_node_name_ips = set_node_healthy_keys(domains_config, deployments_manager)
    dns_healthchecks, dns_records = update_dns_records(deployments_manager, healthy_node_name_ips)
    delete_dns_records(deployments_manager, healthy_node_name_ips, dns_healthchecks, dns_records)


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="nodes_checker",
        sleep_time_between_iterations_seconds=config.NODES_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=False
    )
