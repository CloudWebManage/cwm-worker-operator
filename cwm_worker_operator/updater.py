import time
import datetime

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


def check_update_release(domains_config, updater_metrics, deployments_manager, namespace_name, last_updated, status, app_version, revision):
    start_time = datetime.datetime.now()
    domain_name = namespace_name.replace("--", ".")
    hours_since_last_update = (datetime.datetime.now() - last_updated).total_seconds() / 60 / 60
    is_deployed = status == "deployed"
    if not is_deployed:
        if hours_since_last_update >= .5 and revision <= 2:
            domains_config.set_worker_force_update(domain_name)
            updater_metrics.not_deployed_force_update(domain_name, start_time)
    else:
        worker_metrics = deployments_manager.get_worker_metrics(namespace_name)
        metric_key = 'network_receive_bytes_total_last_{}'.format(config.FORCE_DELETE_NETWORK_RECEIVE_PERIOD)
        assert metric_key in worker_metrics, "missing metric {} for namespace {}".format(metric_key, namespace_name)
        if hours_since_last_update >= config.FORCE_DELETE_GRACE_PERIOD_HOURS and worker_metrics[metric_key] <= config.FORCE_DELETE_MAX_PERIOD_VALUE:
            domains_config.set_worker_force_delete(domain_name)
            updater_metrics.force_delete(domain_name, start_time)
        elif hours_since_last_update >= config.FORCE_UPDATE_MAX_HOURS_TTL:
            domains_config.set_worker_force_update(domain_name)
            updater_metrics.force_update(domain_name, start_time)


def run_single_iteration(domains_config, updater_metrics, deployments_manager):
    for release in deployments_manager.iterate_all_releases():
        namespace_name = release["namespace"]
        datestr, timestr, *_ = release["updated"].split(" ")
        last_updated = datetime.datetime.strptime("{}T{}".format(datestr, timestr.split(".")[0]), "%Y-%m-%dT%H:%M:%S")
        status = release["status"]
        app_version = release["app_version"]
        revision = release["revision"]
        check_update_release(domains_config, updater_metrics, deployments_manager, namespace_name, last_updated, status, app_version, revision)


def start_daemon(once=False, with_prometheus=True, updater_metrics=None, domains_config=None, deployments_manager=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_UPDATER)
    if updater_metrics is None:
        updater_metrics = metrics.UpdaterMetrics()
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    while True:
        run_single_iteration(domains_config, updater_metrics, deployments_manager)
        if once:
            break
        time.sleep(config.UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
