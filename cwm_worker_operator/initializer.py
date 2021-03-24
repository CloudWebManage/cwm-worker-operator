import time
import pytz
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig


def initialize_domain(domains_config, initializer_metrics, domain_name, force_update=False):
    start_time = datetime.datetime.now(pytz.UTC)
    log_kwargs = {"domain_name": domain_name, "start_time": start_time}
    logs.debug("Start initialize_domain", debug_verbosity=4, **log_kwargs)
    try:
        try:
            volume_config = domains_config.get_cwm_api_volume_config(domain_name, initializer_metrics, force_update=force_update)
            namespace_name = volume_config["hostname"].replace(".", "--")
            volume_zone = volume_config["zone"]
        except Exception:
            if config.DEBUG and config.DEBUG_VERBOSITY > 5:
                traceback.print_exc()
            initializer_metrics.failed_to_get_volume_config(domain_name, start_time)
            error_attempt_number = domains_config.increment_worker_error_attempt_number(domain_name)
            if error_attempt_number >= config.WORKER_ERROR_MAX_ATTEMPTS:
                domains_config.set_worker_error(domain_name, domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            return
        if volume_zone != config.CWM_ZONE:
            if config.DEBUG and config.DEBUG_VERBOSITY > 5:
                print("ERROR! Invalid volume zone (domain={} volume_zone={} CWM_ZONE={})".format(domain_name, volume_zone, config.CWM_ZONE), flush=True)
            domains_config.set_worker_error(domain_name, domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE)
            initializer_metrics.invalid_volume_zone(domain_name, start_time)
            logs.debug_info("Invalid volume zone", **log_kwargs)
            return
        initializer_metrics.initialized(domain_name, start_time)
        domains_config.set_worker_ready_for_deployment(domain_name)
        logs.debug_info("Ready for deployment", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        initializer_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, initializer_metrics):
    domain_names_ready_for_deployment = domains_config.get_worker_domains_ready_for_deployment()
    domain_names_waiting_for_deployment_complete = domains_config.get_worker_domains_waiting_for_deployment_complete()
    domains_waiting_for_initialization = domains_config.get_worker_domains_waiting_for_initlization()
    domains_force_update = domains_config.get_domains_force_update()
    for domain_name in domains_force_update:
        if domain_name not in domain_names_ready_for_deployment and domain_name not in domain_names_waiting_for_deployment_complete:
            initialize_domain(domains_config, initializer_metrics, domain_name, force_update=True)
    for domain_name in domains_waiting_for_initialization:
        if domain_name not in domain_names_ready_for_deployment and domain_name not in domain_names_waiting_for_deployment_complete and domain_name not in domains_force_update:
            initialize_domain(domains_config, initializer_metrics, domain_name)


def start_daemon(once=False, with_prometheus=True, initializer_metrics=None, domains_config=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_INITIALIZER)
    if not initializer_metrics:
        initializer_metrics = metrics.InitializerMetrics()
    if not domains_config:
        domains_config = DomainsConfig()
    while True:
        run_single_iteration(domains_config, initializer_metrics)
        if once:
            break
        time.sleep(config.INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
