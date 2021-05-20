import traceback

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import VolumeConfig, VolumeConfigGatewayTypeS3


def failed_to_get_volume_config(domains_config, initializer_metrics, hostname, start_time):
    initializer_metrics.failed_to_get_volume_config(hostname, start_time)
    error_attempt_number = domains_config.increment_worker_error_attempt_number(hostname)
    if error_attempt_number >= config.WORKER_ERROR_MAX_ATTEMPTS:
        domains_config.set_worker_error_by_hostname(hostname, domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
    logs.debug_info("Failed to get volume config", hostname=hostname, start_time=start_time)


def initialize_worker(domains_config, initializer_metrics, worker_id, volume_config: VolumeConfig, start_time, hostname=None):
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
                domains_config.set_worker_error_by_hostname(hostname, domains_config.WORKER_ERROR_INVALID_VOLUME_ZONE)
            else:
                domains_config.del_worker_force_update(worker_id)
                domains_config.set_worker_force_delete(worker_id)
            initializer_metrics.invalid_volume_zone(worker_id, start_time)
            logs.debug_info("Invalid volume zone", **log_kwargs)
            return
        domains_config.del_worker_force_update(worker_id)
        initializer_metrics.initialized(worker_id, start_time)
        domains_config.set_worker_ready_for_deployment(worker_id)
        logs.debug_info("Ready for deployment", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        initializer_metrics.exception(worker_id, start_time)


def run_single_iteration(domains_config, metrics, **_):
    initializer_metrics = metrics
    worker_ids_ready_for_deployment = domains_config.get_worker_ids_ready_for_deployment()
    worker_ids_waiting_for_deployment_complete = domains_config.get_worker_ids_waiting_for_deployment_complete()
    hostnames_waiting_for_initialization = domains_config.get_hostnames_waiting_for_initlization()
    worker_ids_force_update = domains_config.get_worker_ids_force_update()
    hostnames_forced_update = set()
    for worker_id in worker_ids_force_update:
        start_time = common.now()
        if worker_id not in worker_ids_ready_for_deployment and worker_id not in worker_ids_waiting_for_deployment_complete:
            volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id, metrics=initializer_metrics, force_update=True)
            for hostname in volume_config.hostnames:
                hostnames_forced_update.add(hostname)
            initialize_worker(domains_config, initializer_metrics, worker_id, volume_config, start_time)
    for hostname in hostnames_waiting_for_initialization:
        if hostname not in hostnames_forced_update:
            start_time = common.now()
            volume_config = domains_config.get_cwm_api_volume_config(hostname=hostname, metrics=initializer_metrics)
            worker_id = volume_config.id
            if not worker_id or volume_config._error:
                if config.DEBUG and config.DEBUG_VERBOSITY >= 5:
                    print(volume_config)
                failed_to_get_volume_config(domains_config, initializer_metrics, hostname, start_time)
            elif worker_id not in worker_ids_ready_for_deployment and worker_id not in worker_ids_waiting_for_deployment_complete and worker_id not in worker_ids_force_update:
                initialize_worker(domains_config, initializer_metrics, worker_id, volume_config, start_time, hostname=hostname)


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
