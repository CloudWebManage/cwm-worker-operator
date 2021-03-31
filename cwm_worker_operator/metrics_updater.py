import time
import traceback
from collections import defaultdict

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import common


DATEFORMAT = "%Y%m%d%H%M%S"
LAST_UPDATE_KEY = 'lu'
MINUTES_KEY = 'm'
TIMESTAMP_KEY = 't'


def update_agg_metrics(agg_metrics, now, current_metrics, limit=20):
    agg_metrics[LAST_UPDATE_KEY] = now.strftime(DATEFORMAT)
    current_metrics[TIMESTAMP_KEY] = now.strftime(DATEFORMAT)
    agg_metrics.setdefault(MINUTES_KEY, []).append(current_metrics)
    if len(agg_metrics[MINUTES_KEY]) > limit:
        agg_metrics[MINUTES_KEY] = agg_metrics[MINUTES_KEY][1:limit+1]


def get_deployment_api_metrics(domains_config, namespace_name, buckets=('http', 'https')):
    values = defaultdict(float)
    for bucket in buckets:
        for metric, value in domains_config.get_deployment_api_metrics(namespace_name, bucket).items():
            try:
                if '.' in str(value):
                    value = float(value)
                else:
                    value = int(value)
            except:
                value = None
            if value:
                values[metric] += value
    return dict(values)


def get_metrics(domains_config, deployments_manager, namespace_name):
    domain_name = namespace_name.replace('--', '.')
    return {
        'disk_usage_bytes': domains_config.get_worker_total_used_bytes(domain_name),
        **get_deployment_api_metrics(domains_config, namespace_name),
        **deployments_manager.get_prometheus_metrics(namespace_name),
        **deployments_manager.get_kube_metrics(namespace_name),
    }


def update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, namespace_name, now=None, update_interval_seconds=30):
    start_time = common.now()
    domain_name = namespace_name.replace("--", ".")
    try:
        agg_metrics = domains_config.get_worker_aggregated_metrics(domain_name, clear=True)
        if agg_metrics:
            last_agg_update = common.strptime(agg_metrics[LAST_UPDATE_KEY], DATEFORMAT)
        else:
            last_agg_update = None
            agg_metrics = {}
        if now is None:
            now = common.now()
        if not last_agg_update or (now - last_agg_update).total_seconds() >= update_interval_seconds:
            update_agg_metrics(agg_metrics, now, get_metrics(domains_config, deployments_manager, namespace_name))
            metrics_updater_metrics.agg_metrics_update(domain_name, start_time)
        domains_config.set_worker_aggregated_metrics(domain_name, agg_metrics)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        metrics_updater_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, metrics_updater_metrics, deployments_manager):
    for release in deployments_manager.iterate_all_releases():
        update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, release["namespace"])


def start_daemon(once=False, with_prometheus=True, metrics_updater_metrics=None, domains_config=None, deployments_manager=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_METRICS_UPDATER)
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
