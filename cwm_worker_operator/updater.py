import time
import pytz
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import metrics_updater
from cwm_worker_operator.cwm_api_manager import CwmApiManager


def check_worker_force_delete_from_metrics(namespace_name, domains_config):
    last_action = domains_config.get_deployment_last_action(namespace_name)
    if last_action:
        return (datetime.datetime.now(pytz.UTC) - last_action).total_seconds() / 60 >= config.FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES
    else:
        return True


def check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision):
    start_time = datetime.datetime.now(pytz.UTC)
    domain_name = namespace_name.replace("--", ".")
    volume_config = domains_config.get_cwm_api_volume_config(domain_name)
    disable_force_delete = volume_config.get("disable_force_delete")
    disable_force_update = volume_config.get("disable_force_update")
    try:
        hours_since_last_update = (datetime.datetime.now(pytz.UTC) - last_updated).total_seconds() / 60 / 60
        is_deployed = status == "deployed"
        if not is_deployed:
            if hours_since_last_update >= .5 and revision <= 2:
                msg = "domain force update (first revision)"
                if disable_force_update:
                    logs.debug("{} but disable_force_update is true".format(msg), debug_verbosity=10, domain_name=domain_name, start_time=start_time, hours_since_last_update=hours_since_last_update)
                else:
                    logs.debug(msg, debug_verbosity=4, domain_name=domain_name, start_time=start_time, hours_since_last_update=hours_since_last_update)
                    domains_config.set_worker_force_update(domain_name)
                    updater_metrics.not_deployed_force_update(domain_name, start_time)
        else:
            if hours_since_last_update >= config.FORCE_DELETE_GRACE_PERIOD_HOURS and check_worker_force_delete_from_metrics(namespace_name, domains_config):
                msg = "domain force delete (after grace period + based on metrics)"
                if disable_force_delete:
                    logs.debug("{} but disable_force_delete is true".format(msg), debug_verbosity=10, domain_name=domain_name, start_time=start_time, hours_since_last_update=hours_since_last_update)
                else:
                    logs.debug(msg, debug_verbosity=4, domain_name=domain_name, start_time=start_time, hours_since_last_update=hours_since_last_update)
                    domains_config.set_worker_force_delete(domain_name)
                    updater_metrics.force_delete(domain_name, start_time)
            elif hours_since_last_update >= config.FORCE_UPDATE_MAX_HOURS_TTL:
                msg = "domain force update (after FORCE_UPDATE_MAX_HOURS_TTL)"
                if disable_force_update:
                    logs.debug("{} but disable_force_update is true".format(msg), debug_verbosity=10, domain_name=domain_name, start_time=start_time, hours_since_last_update=hours_since_last_update)
                else:
                    logs.debug(msg, debug_verbosity=4, domain_name=domain_name, start_time=start_time, hours_since_last_update=hours_since_last_update)
                    domains_config.set_worker_force_update(domain_name)
                    updater_metrics.force_update(domain_name, start_time)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        updater_metrics.exception(domain_name, start_time)
    return domain_name, start_time


def send_agg_metrics(domains_config, updater_metrics, domain_name, start_time, cwm_api_manager):
    try:
        agg_metrics = domains_config.get_worker_aggregated_metrics(domain_name)
        if agg_metrics:
            current_last_update = datetime.datetime.strptime(agg_metrics.get(metrics_updater.LAST_UPDATE_KEY), metrics_updater.DATEFORMAT).astimezone(pytz.UTC)
            current_minutes = agg_metrics.get(metrics_updater.MINUTES_KEY)
            if current_last_update and current_minutes:
                previous_last_update_sent, previous_last_update = domains_config.get_worker_aggregated_metrics_last_sent_update(domain_name)
                if previous_last_update_sent and (datetime.datetime.now(pytz.UTC) - previous_last_update_sent).total_seconds() < 60:
                    logs.debug('send_agg_metrics: not sending metrics to cwm_api because last update was sent less than 60 seconds ago', debug_verbosity=10, domain_name=domain_name, previous_last_update_sent=previous_last_update_sent)
                elif previous_last_update and previous_last_update == current_last_update:
                    logs.debug('send_agg_metrics: not sending metrics because previous last_update is the same as current last_update', debug_verbosity=10, domain_name=domain_name, previous_last_update=previous_last_update, current_last_update=current_last_update)
                else:
                    logs.debug('send_agg_metrics: sending metrics to cwm_api', debug_verbosity=9, domain_name=domain_name, current_last_update=current_last_update)
                    cwm_api_manager.send_agg_metrics(domain_name, current_minutes)
                    domains_config.set_worker_aggregated_metrics_last_sent_update(domain_name, current_last_update)
            else:
                logs.debug('send_agg_metrics: no last_update or minutes available for domain', debug_verbosity=10, domain_name=domain_name)
        else:
            logs.debug('send_agg_metrics: no agg_metrics for domain', debug_verbosity=10, domain_name=domain_name)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), domain_name=domain_name, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        updater_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager):
    for release in deployments_manager.iterate_all_releases():
        namespace_name = release["namespace"]
        datestr, timestr, *_ = release["updated"].split(" ")
        last_updated = datetime.datetime.strptime("{}T{}".format(datestr, timestr.split(".")[0]), "%Y-%m-%dT%H:%M:%S").astimezone(pytz.UTC)
        status = release["status"]
        # app_version = release["app_version"]
        revision = int(release["revision"])
        domain_name, start_time = check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision)
        send_agg_metrics(domains_config, updater_metrics, domain_name, start_time, cwm_api_manager)


def start_daemon(once=False, with_prometheus=True, updater_metrics=None, domains_config=None, deployments_manager=None, cwm_api_manager=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_UPDATER)
    if updater_metrics is None:
        updater_metrics = metrics.UpdaterMetrics()
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    if cwm_api_manager is None:
        cwm_api_manager = CwmApiManager()
    while True:
        run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
        if once:
            break
        time.sleep(config.UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
