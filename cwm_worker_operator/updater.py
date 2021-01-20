import time
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import metrics_updater


def check_worker_force_delete_from_metrics(namespace_name, domains_config):
    last_action = domains_config.get_deployment_last_action(namespace_name)
    if last_action:
        return (datetime.datetime.now() - last_action).total_seconds() / 60 >= config.FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES
    else:
        return True


def check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision):
    start_time = datetime.datetime.now()
    domain_name = namespace_name.replace("--", ".")
    try:
        hours_since_last_update = (datetime.datetime.now() - last_updated).total_seconds() / 60 / 60
        is_deployed = status == "deployed"
        if not is_deployed:
            if hours_since_last_update >= .5 and revision <= 2:
                domains_config.set_worker_force_update(domain_name)
                updater_metrics.not_deployed_force_update(domain_name, start_time)
        else:
            if hours_since_last_update >= config.FORCE_DELETE_GRACE_PERIOD_HOURS and check_worker_force_delete_from_metrics(namespace_name, domains_config):
                domains_config.set_worker_force_delete(domain_name)
                updater_metrics.force_delete(domain_name, start_time)
            elif hours_since_last_update >= config.FORCE_UPDATE_MAX_HOURS_TTL:
                domains_config.set_worker_force_update(domain_name)
                updater_metrics.force_update(domain_name, start_time)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        updater_metrics.exception(domain_name, start_time)
    return domain_name, start_time


def send_agg_metrics_to_cwm(domain_name, last_update, minutes):
    # TBD
    pass


def store_agg_metrics(domains_config, updater_metrics, domain_name, start_time):
    try:
        agg_metrics = domains_config.get_worker_aggregated_metrics(domain_name, clear=True)
        if agg_metrics:
            last_update = agg_metrics.get(metrics_updater.LAST_UPDATE_KEY)
            minutes = agg_metrics.get(metrics_updater.MINUTES_KEY)
            if last_update and minutes:
                send_agg_metrics_to_cwm(domain_name, last_update, minutes)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        updater_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, updater_metrics, deployments_manager):
    for release in deployments_manager.iterate_all_releases():
        namespace_name = release["namespace"]
        datestr, timestr, *_ = release["updated"].split(" ")
        last_updated = datetime.datetime.strptime("{}T{}".format(datestr, timestr.split(".")[0]), "%Y-%m-%dT%H:%M:%S")
        status = release["status"]
        # app_version = release["app_version"]
        revision = int(release["revision"])
        domain_name, start_time = check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision)
        store_agg_metrics(domains_config, updater_metrics, domain_name, start_time)


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
