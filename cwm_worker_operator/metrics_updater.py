import time
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


DATEFORMAT = "%Y%m%d%H%M%S"
LAST_UPDATE_KEY = 'lu'
TEN_MINUTES_KEY = 'm'
HOURS_KEY = 'h'
DAYS_KEY = 'd'
VALUES_KEY = 'v'


def update_agg_metrics_key(agg_metrics, key, now, period_minutes, current_metrics, limit):
    metrics_obj = agg_metrics.setdefault(key, {})
    if LAST_UPDATE_KEY not in metrics_obj or (now - datetime.datetime.strptime(metrics_obj[LAST_UPDATE_KEY], DATEFORMAT)).total_seconds() >= 60 * period_minutes:
        metrics_obj[LAST_UPDATE_KEY] = now.strftime(DATEFORMAT)
        metrics_obj.setdefault(VALUES_KEY, []).append(current_metrics)
        if len(metrics_obj[VALUES_KEY]) > limit:
            metrics_obj[VALUES_KEY].pop(0)


def update_agg_metrics(agg_metrics, now, current_metrics):
    agg_metrics[LAST_UPDATE_KEY] = now.strftime(DATEFORMAT)
    update_agg_metrics_key(agg_metrics, TEN_MINUTES_KEY, now, 10, current_metrics, config.METRICS_UPDATER_TEN_MINUTES_RETENTION_SIZE)
    update_agg_metrics_key(agg_metrics, HOURS_KEY, now, 60, current_metrics, config.METRICS_UPDATER_HOURS_RETENTION_SIZE)
    update_agg_metrics_key(agg_metrics, DAYS_KEY, now, 60 * 24, current_metrics, config.METRICS_UPDATER_DAYS_RETENTION_SIZE)


def update_release_metrics(domains_config, metrics_updater_metrics, namespace_name):
    start_time = datetime.datetime.now()
    domain_name = namespace_name.replace("--", ".")
    try:
        agg_metrics = domains_config.get_worker_aggregated_metrics(domain_name)
        if agg_metrics:
            last_agg_update = datetime.datetime.strptime(agg_metrics[LAST_UPDATE_KEY], DATEFORMAT)
        else:
            last_agg_update = None
            agg_metrics = {}
        now = datetime.datetime.now()
        if not last_agg_update or (now - last_agg_update).total_seconds() >= 60:
            update_agg_metrics(agg_metrics, now, domains_config.get_deployment_api_metrics(namespace_name))
            domains_config.set_worker_aggregated_metrics(domain_name, agg_metrics)
            metrics_updater_metrics.agg_metrics_update(domain_name, start_time)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        metrics_updater_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, metrics_updater_metrics, deployments_manager):
    for release in deployments_manager.iterate_all_releases():
        update_release_metrics(domains_config, metrics_updater_metrics, release["namespace"])


def start_daemon(once=False, with_prometheus=True, metrics_updater_metrics=None, domains_config=None, deployments_manager=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_UPDATER)
    if metrics_updater_metrics is None:
        metrics_updater_metrics = metrics.MetricsUpdaterMetrics()
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    while True:
        run_single_iteration(domains_config, metrics_updater_metrics, deployments_manager)
        if once:
            break
        time.sleep(config.METRICS_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
