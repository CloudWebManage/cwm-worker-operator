import time
import datetime
import requests
import urllib3

import prometheus_client

import cwm_worker_deployment.deployment
from cwm_worker_operator import common
from cwm_worker_operator import metrics
from cwm_worker_operator import config
from cwm_worker_operator import logs


urllib3.disable_warnings()


def check_deployment_complete(redis_pool, waiter_metrics, domain_name):
    start_time = config.get_worker_ready_for_deployment_start_time(redis_pool, domain_name)
    log_kwargs = {"domain_name": domain_name, "start_time": start_time}
    volume_config, namespace_name = common.get_volume_config_namespace_from_domain(redis_pool, waiter_metrics, domain_name)
    if not namespace_name:
        waiter_metrics.failed_to_get_volume_config(domain_name, start_time)
        logs.debug_info("Failed to get volume config", **log_kwargs)
        return
    if cwm_worker_deployment.deployment.is_ready(namespace_name, "minio"):
        hostname = cwm_worker_deployment.deployment.get_hostname(namespace_name, "minio")
        ok = True
        if config.WAITER_VERIFY_WORKER_ACCESS:
            for proto in ["http", "https"]:
                url = {"http": "http://{}:8080".format(hostname), "https": "https://{}:8443".format(hostname)}[proto]
                requests_kwargs = {"http": {}, "https": {"verify": False}}[proto]
                try:
                    res = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=2, **requests_kwargs)
                except Exception as e:
                    logs.debug("Failed {} readiness check".format(proto), debug_verbosity=3, exception=str(e), **log_kwargs)
                    res = None
                if not res:
                    ok = False
                elif res.status_code != 200:
                    logs.debug("Failed {} readiness check".format(proto), debug_verbosity=3, status_code=res.status_code, **log_kwargs)
                    ok = False
                elif '<title>MinIO Browser</title>' not in res.text:
                    logs.debug("Failed {} readiness check".format(proto), debug_verbosity=3, missing_title=True, **log_kwargs)
                    ok = False
        if ok:
            config.set_worker_available(
                redis_pool, domain_name,
                cwm_worker_deployment.deployment.get_hostname(namespace_name, "minio")
            )
            waiter_metrics.deployment_success(domain_name, start_time)
            logs.debug_info("Success", **log_kwargs)
            return
    if (datetime.datetime.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS:
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
        waiter_metrics.deployment_timeout(domain_name, start_time)
        logs.debug_info("timeout", **log_kwargs)


def run_single_iteration(redis_pool, waiter_metrics):
    for domain_name in config.get_worker_domains_waiting_for_deployment_complete(redis_pool):
        check_deployment_complete(redis_pool, waiter_metrics, domain_name)


def start_daemon(once=False):
    prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_WAITER)
    waiter_metrics = metrics.WaiterMetrics()
    redis_pool = config.get_redis_pool()
    while True:
        run_single_iteration(redis_pool, waiter_metrics)
        if once:
            break
        time.sleep(config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
