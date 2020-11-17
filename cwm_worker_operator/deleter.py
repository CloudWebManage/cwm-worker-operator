import time
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import logs
from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


def delete(domain_name, deployment_timeout_string=None, delete_namespace=None, delete_helm=None,
           domains_config=None, deployments_manager=None):
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    if delete_namespace is None:
        delete_namespace = config.DELETER_DEFAULT_DELETE_NAMESPACE
    if delete_helm is None:
        delete_helm = config.DELETER_DEFAULT_DELETE_HELM
    volume_config = domains_config.get_cwm_api_volume_config(domain_name)
    namespace_name = volume_config.get("hostname", domain_name).replace(".", "--")
    domains_config.del_worker_keys(None, domain_name)
    deployments_manager.delete(
        namespace_name, "minio", timeout_string=deployment_timeout_string, delete_namespace=delete_namespace,
        delete_helm=delete_helm
    )


def run_single_iteration(domains_config, deleter_metrics, deployments_manager):
    for domain_name in domains_config.iterate_domains_to_delete():
        start_time = datetime.datetime.now()
        try:
            delete(domain_name, domains_config=domains_config, deployments_manager=deployments_manager)
            deleter_metrics.delete_success(domain_name, start_time)
        except Exception as e:
            logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
            if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                traceback.print_exc()
            deleter_metrics.exception(domain_name, start_time)


def start_daemon(once=False, with_prometheus=True, deleter_metrics=None, domains_config=None, deployments_manager=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_DELETER)
    if not deleter_metrics:
        deleter_metrics = metrics.DeleterMetrics()
    if not domains_config:
        domains_config = DomainsConfig()
    if not deployments_manager:
        deployments_manager = DeploymentsManager()
    while True:
        run_single_iteration(domains_config, deleter_metrics, deployments_manager)
        if once:
            break
        time.sleep(config.DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
