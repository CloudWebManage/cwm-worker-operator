import traceback

from cwm_worker_operator import metrics
from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator import domains_config
from cwm_worker_operator.daemon import Daemon


def check_deployment_complete(domains_config, waiter_metrics, deployments_manager, worker_id):
    start_time = domains_config.get_worker_ready_for_deployment_start_time(worker_id)
    log_kwargs = {"worker_id": worker_id, "start_time": start_time}
    # this log occurs on every iteration of waiter, so it should be at debug verbosity 10 otherwise there is a flood of logs
    logs.debug("Start check_deployment_complete", debug_verbosity=10, **log_kwargs)
    try:
        volume_config, namespace_name = domains_config.get_volume_config_namespace_from_worker_id(waiter_metrics, worker_id)
        if not namespace_name:
            waiter_metrics.failed_to_get_volume_config(worker_id, start_time)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            return
        if volume_config.get("protocol", "http") == "https" and volume_config.get("certificate_key") and volume_config.get("certificate_pem"):
            enabledProtocols = ['http', 'https']
        else:
            enabledProtocols = ['http']
        if deployments_manager.is_ready(namespace_name, "minio", enabledProtocols=enabledProtocols):
            internal_hostname = deployments_manager.get_hostname(namespace_name, "minio")
            ok = True
            if config.WAITER_VERIFY_WORKER_ACCESS:
                ok = deployments_manager.verify_worker_access(internal_hostname, log_kwargs)
            if ok:
                domains_config.set_worker_available(worker_id, internal_hostname)
                waiter_metrics.deployment_success(worker_id, start_time)
                logs.debug_info("Success", **log_kwargs)
                return
        if (common.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS:
            domains_config.set_worker_error(worker_id, domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
            waiter_metrics.deployment_timeout(worker_id, start_time)
            logs.debug_info("timeout", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        waiter_metrics.exception(worker_id, start_time)


def run_single_iteration(domains_config: domains_config.DomainsConfig, metrics, deployments_manager, **_):
    waiter_metrics = metrics
    for worker_id in domains_config.get_worker_ids_waiting_for_deployment_complete():
        check_deployment_complete(domains_config, waiter_metrics, deployments_manager, worker_id)


def start_daemon(once=False, with_prometheus=True, waiter_metrics=None, domains_config=None):
    Daemon(
        name='waiter',
        sleep_time_between_iterations_seconds=config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.WaiterMetrics,
        domains_config=domains_config,
        metrics=waiter_metrics,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_WAITER
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
