import time
import datetime
import requests
import urllib3

import prometheus_client

import cwm_worker_deployment.deployment
from cwm_worker_operator import common
from cwm_worker_operator import metrics
from cwm_worker_operator import config


urllib3.disable_warnings()


def check_deployment_complete(redis_pool, waiter_metrics, domain_name):
    start_time = config.get_worker_ready_for_deployment_start_time(redis_pool, domain_name)
    volume_config, namespace_name = common.get_volume_config_namespace_from_domain(redis_pool, waiter_metrics, domain_name)
    if not namespace_name:
        waiter_metrics.failed_to_get_volume_config(domain_name, start_time)
        if config.DEBUG:
            print("Failed to get volume config (domain={})".format(domain_name), flush=True)
        return
    if cwm_worker_deployment.deployment.is_ready(namespace_name, "minio"):
        hostname = cwm_worker_deployment.deployment.get_hostname(namespace_name, "minio")
        if config.WAITER_VERIFY_WORKER_ACCESS:
            ok = False
            try:
                res = requests.get("http://{}:8080".format(hostname), headers={"User-Agent":"Mozilla"}, timeout=2)
                if res.status_code == 200 and '<title>MinIO Browser</title>' in res.text:
                    res = requests.get("https://{}:8443".format(hostname), headers={"User-Agent":"Mozilla"}, timeout=2, verify=False)
                    if res.status_code == 200 and '<title>MinIO Browser</title>' in res.text:
                        ok = True
            except Exception:
                pass
        else:
            ok = True
        if ok:
            config.set_worker_available(
                redis_pool, domain_name,
                cwm_worker_deployment.deployment.get_hostname(namespace_name, "minio")
            )
            waiter_metrics.deployment_success(domain_name, start_time)
            if config.DEBUG:
                print("success (domain={})".format(domain_name), flush=True)
            return
    if (datetime.datetime.now() - start_time).total_seconds() > config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS:
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT)
        waiter_metrics.deployment_timeout(domain_name, start_time)
        if config.DEBUG:
            print("timeout (domain={})".format(domain_name), flush=True)


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
