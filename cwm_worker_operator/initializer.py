"""
Initializes requests to deploy workers (the first step in deployment process)
"""
import traceback

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import VolumeConfig
from cwm_worker_operator.deployment_flow_manager import InitializerDeploymentFlowManager


def initialize_worker(domains_config, initializer_metrics, flow_manager, worker_id, volume_config: VolumeConfig, start_time, hostname=None):
    worker_to_delete = domains_config.get_worker_force_delete(worker_id)
    if worker_to_delete and not worker_to_delete['allow_cancel']:
        # worker is forced to delete but the deletion cannot be canceled, so we cancel the deployment until delete will occur
        return
    log_kwargs = {"worker_id": worker_id, "start_time": start_time, "hostname": hostname}
    logs.debug("Start initialize_worker", debug_verbosity=4, **log_kwargs)
    try:
        volume_zone = volume_config.zone
        if not volume_config.is_valid_zone_for_cluster and (not volume_config.gateway_updated_for_request_hostname or volume_config.gateway_updated_for_request_hostname.lower() != hostname.lower()):
            if config.DEBUG and config.DEBUG_VERBOSITY > 5:
                print("ERROR! Invalid volume zone (worker_id={} volume_zone={} CWM_ZONE={})".format(worker_id, volume_zone, config.CWM_ZONE), flush=True)
            if hostname:
                flow_manager.set_hostname_error(hostname, domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE, worker_id=worker_id)
            else:
                flow_manager.set_worker_force_delete(worker_id)
            initializer_metrics.invalid_volume_zone(worker_id, start_time)
            logs.debug_info("Invalid volume zone", **log_kwargs)
            return
        if hostname and not common.is_hostnames_match_in_list(hostname, volume_config.hostnames):
            initializer_metrics.invalid_hostname(worker_id, start_time)
            logs.debug_info("Invalid hostname", **log_kwargs)
            flow_manager.set_hostname_error(hostname, domains_config.WORKER_ERROR_INVALID_HOSTNAME, worker_id=worker_id)
            return
        initializer_metrics.initialized(worker_id, start_time)
        flow_manager.set_worker_ready_for_deployment(worker_id)
        logs.debug_info("Ready for deployment", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        initializer_metrics.exception(worker_id, start_time)


def run_single_iteration(domains_config, metrics, **_):
    initializer_metrics = metrics
    flow_manager = InitializerDeploymentFlowManager(domains_config)
    for volume_config, worker_id in flow_manager.iterate_volume_configs_forced_update(initializer_metrics):
        start_time = common.now()
        initialize_worker(domains_config, initializer_metrics, flow_manager, worker_id, volume_config, start_time)
    for volume_config, hostname, failed_to_get_volume_config in flow_manager.iterate_volume_config_hostnames_waiting_for_initialization(initializer_metrics):
        start_time = common.now()
        if failed_to_get_volume_config:
            if config.DEBUG and config.DEBUG_VERBOSITY >= 5:
                print(volume_config)
            initializer_metrics.failed_to_get_volume_config(hostname, start_time)
            flow_manager.set_hostname_error(hostname, domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG, allow_retry=True)
            logs.debug_info("Failed to get volume config", hostname=hostname, start_time=start_time)
        else:
            initialize_worker(domains_config, initializer_metrics, flow_manager, volume_config.id, volume_config, start_time, hostname=hostname)


def start_daemon(once=False, with_prometheus=True, initializer_metrics=None, domains_config=None):
    Daemon(
        name="initializer",
        sleep_time_between_iterations_seconds=config.INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.InitializerMetrics,
        metrics=initializer_metrics,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_INITIALIZER
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
