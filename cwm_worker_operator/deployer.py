import time
import json
import traceback

import prometheus_client

import cwm_worker_deployment.deployment

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import common


def deploy_worker(redis_pool, deployer_metrics, domain_name, debug=False):
    start_time = config.get_worker_ready_for_deployment_start_time(redis_pool, domain_name)
    volume_config, namespace_name = common.get_volume_config_namespace_from_domain(redis_pool, deployer_metrics, domain_name)
    if not namespace_name:
        deployer_metrics.failed_to_get_volume_config(domain_name, start_time)
        if config.DEBUG:
            print("Failed to get volume config (domain={})".format(domain_name), flush=True)
        return
    protocol = volume_config.get("protocol", "http")
    certificate_key = volume_config.get("certificate_key")
    certificate_key = "\n".join(certificate_key) if certificate_key else None
    certificate_pem = volume_config.get("certificate_pem")
    certificate_pem = "\n".join(certificate_pem) if certificate_pem else None
    client_id = volume_config.get("client_id")
    secret = volume_config.get("secret")
    minio_extra_configs = {
        **config.MINIO_EXTRA_CONFIG,
        **volume_config.get("minio_extra_configs", {})
    }
    cwm_worker_deployment_extra_configs = {
        **config.CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG,
        **volume_config.get("cwm_worker_deployment_extra_configs", {})
    }
    extra_objects = [
        *config.CWM_WORKER_EXTRA_OBJECTS,
        *volume_config.get("cwm_worker_extra_objects", [])
    ]
    minio = {"createPullSecret": config.PULL_SECRET}
    if protocol == "https" and certificate_key and certificate_pem:
        minio["enabledProtocols"] = ["http", "https"]
        minio["certificate_pem"] = certificate_pem
        minio["certificate_key"] = certificate_key
    else:
        minio["enabledProtocols"] = ["http"]
        minio["certificate_pem"] = ""
        minio["certificate_key"] = ""
    if client_id and secret:
        minio["access_key"] = client_id
        minio["secret_key"] = secret
    deployment_config_json = json.dumps({
        "cwm-worker-deployment": {
            "type": "minio",
            "namespace": namespace_name,
            **cwm_worker_deployment_extra_configs
        },
        "minio": {
            **minio,
            **minio_extra_configs
        },
        "extraObjects": extra_objects
    }).replace("__NAMESPACE_NAME__", namespace_name)
    if debug:
        print(deployment_config_json, flush=True)
    deployment_config = json.loads(deployment_config_json)
    if debug:
        cwm_worker_deployment.deployment.deploy(deployment_config, dry_run=True)
    try:
        deploy_output = cwm_worker_deployment.deployment.deploy(deployment_config)
    except Exception:
        if debug or (config.DEBUG and config.DEBUG_VERBOSITY > 5):
            traceback.print_exc()
            print("ERROR! Failed to deploy (namespace={})".format(namespace_name), flush=True)
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_FAILED_TO_DEPLOY)
        deployer_metrics.deploy_failed(domain_name, start_time)
        if config.DEBUG:
            print("Failed to deploy (domain={})".format(domain_name), flush=True)
        return
    if config.DEBUG and config.DEBUG_VERBOSITY > 5:
        print(deploy_output, flush=True)
    deployer_metrics.deploy_success(domain_name, start_time)
    config.set_worker_waiting_for_deployment(redis_pool, domain_name)
    if config.DEBUG:
        print("Deploy success (domain={})".format(domain_name), flush=True)


def run_single_iteration(redis_pool, deployer_metrics):
    domain_names_waiting_for_deployment_complete = config.get_worker_domains_waiting_for_deployment_complete(redis_pool)
    for domain_name in config.get_worker_domains_ready_for_deployment(redis_pool):
        if domain_name not in domain_names_waiting_for_deployment_complete:
            deploy_worker(redis_pool, deployer_metrics, domain_name)


def start_daemon(once=False):
    prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_DEPLOYER)
    common.init_cache()
    deployer_metrics = metrics.DeployerMetrics()
    redis_pool = config.get_redis_pool()
    while True:
        run_single_iteration(redis_pool, deployer_metrics)
        if once:
            break
        time.sleep(config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
