import time
import datetime
import traceback

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs


def initialize_domain(redis_pool, initializer_metrics, domain_name):
    start_time = datetime.datetime.now()
    log_kwargs = {"domain_name": domain_name, "start_time": start_time}
    try:
        volume_config = config.get_cwm_api_volume_config(redis_pool, domain_name, initializer_metrics)
        namespace_name = volume_config["hostname"].replace(".", "--")
        volume_zone = volume_config["zone"]
    except Exception:
        if config.DEBUG and config.DEBUG_VERBOSITY > 5:
            traceback.print_exc()
        initializer_metrics.failed_to_get_volume_config(domain_name, start_time)
        error_attempt_number = config.increment_worker_error_attempt_number(redis_pool, domain_name)
        if error_attempt_number >= config.WORKER_ERROR_MAX_ATTEMPTS:
            config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
        logs.debug_info("Failed to get volume config", **log_kwargs)
        return
    if volume_zone != config.CWM_ZONE:
        if config.DEBUG and config.DEBUG_VERBOSITY > 5:
            print("ERROR! Invalid volume zone (domain={} volume_zone={} CWM_ZONE={})".format(domain_name, volume_zone, config.CWM_ZONE), flush=True)
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_INVALID_VOLUME_ZONE)
        initializer_metrics.invalid_volume_zone(domain_name, start_time)
        logs.debug_info("Invalid volume zone", **log_kwargs)
        return
    initializer_metrics.initialized(domain_name, start_time)
    config.set_worker_ready_for_deployment(redis_pool, domain_name)
    logs.debug_info("Ready for deployment", **log_kwargs)


def run_single_iteration(redis_pool, initializer_metrics):
    domain_names_ready_for_deployment = config.get_worker_domains_ready_for_deployment(redis_pool)
    domain_names_waiting_for_deployment_complete = config.get_worker_domains_waiting_for_deployment_complete(redis_pool)
    for domain_name in config.get_worker_domains_waiting_for_initlization(redis_pool):
        if domain_name not in domain_names_ready_for_deployment and domain_name not in domain_names_waiting_for_deployment_complete:
            initialize_domain(redis_pool, initializer_metrics, domain_name)


def start_daemon(once=False):
    prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_INITIALIZER)
    initializer_metrics = metrics.InitializerMetrics()
    redis_pool = config.get_redis_pool()
    while True:
        run_single_iteration(redis_pool, initializer_metrics)
        if once:
            break
        time.sleep(config.INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
