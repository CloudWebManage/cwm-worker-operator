import time
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import metrics
from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


def check_deployment_complete(domains_config, waiter_metrics, deployments_manager, domain_name):
    start_time = domains_config.get_worker_ready_for_deployment_start_time(domain_name)
    log_kwargs = {"domain_name": domain_name, "start_time": start_time}
    logs.debug("Start check_deployment_complete", debug_verbosity=4, **log_kwargs)
    try:
        volume_config, namespace_name = domains_config.get_volume_config_namespace_from_domain(waiter_metrics, domain_name)
        if not namespace_name:
            waiter_metrics.failed_to_get_volume_config(domain_name, start_time)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            return
        if deployments_manager.is_ready(namespace_name, "minio"):
            hostname = deployments_manager.get_hostname(namespace_name, "minio")
            ok = True
            if config.WAITER_VERIFY_WORKER_ACCESS:
                ok = deployments_manager.verify_worker_access(hostname, log_kwargs)
            if ok:
                domains_config.set_worker_available(domain_name, deployments_manager.get_hostname(namespace_name, "minio"))
                waiter_metrics.deployment_success(domain_name, start_time)
                logs.debug_info("Success", **log_kwargs)
                return
        if (datetime.datetime.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS:
            domains_config.set_worker_error(domain_name, domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
            waiter_metrics.deployment_timeout(domain_name, start_time)
            logs.debug_info("timeout", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        waiter_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, waiter_metrics, deployments_manager):
    for domain_name in domains_config.get_worker_domains_waiting_for_deployment_complete():
        check_deployment_complete(domains_config, waiter_metrics, deployments_manager, domain_name)


def start_daemon(once=False, with_prometheus=True, waiter_metrics=None, domains_config=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_WAITER)
    if waiter_metrics is None:
        waiter_metrics = metrics.WaiterMetrics()
    if domains_config is None:
        domains_config = DomainsConfig()
    deployments_manager = DeploymentsManager()
    while True:
        run_single_iteration(domains_config, waiter_metrics, deployments_manager)
        if once:
            break
        time.sleep(config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
