import traceback

from cwm_worker_operator import metrics
from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon


def check_deployment_complete(domains_config, waiter_metrics, deployments_manager, domain_name):
    start_time = domains_config.get_worker_ready_for_deployment_start_time(domain_name)
    log_kwargs = {"domain_name": domain_name, "start_time": start_time}
    # this log occurs on every iteration of waiter, so it should be at debug verbosity 10 otherwise there is a flood of logs
    logs.debug("Start check_deployment_complete", debug_verbosity=10, **log_kwargs)
    try:
        volume_config, namespace_name = domains_config.get_volume_config_namespace_from_domain(waiter_metrics, domain_name)
        if not namespace_name:
            waiter_metrics.failed_to_get_volume_config(domain_name, start_time)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            return
        if deployments_manager.is_ready(namespace_name, "minio"):
            hostname = deployments_manager.get_hostname(namespace_name, "minio")
            ok = True
            if config.WAITER_VERIFY_WORKER_ACCESS:
                ok = deployments_manager.verify_worker_access(hostname, log_kwargs)
            if ok:
                domains_config.set_worker_available(domain_name, deployments_manager.get_hostname(namespace_name, "minio"))
                waiter_metrics.deployment_success(domain_name, start_time)
                logs.debug_info("Success", **log_kwargs)
                return
        if (common.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS:
            domains_config.set_worker_error(domain_name, domains_config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
            waiter_metrics.deployment_timeout(domain_name, start_time)
            logs.debug_info("timeout", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        waiter_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, metrics, deployments_manager, **_):
    waiter_metrics = metrics
    for domain_name in domains_config.get_worker_domains_waiting_for_deployment_complete():
        check_deployment_complete(domains_config, waiter_metrics, deployments_manager, domain_name)


def start_daemon(once=False, with_prometheus=True, waiter_metrics=None, domains_config=None):
    Daemon(
        name='waiter',
        sleep_time_between_iterations_seconds=config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.WaiterMetrics(),
        domains_config=domains_config,
        metrics=waiter_metrics,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_WAITER
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
