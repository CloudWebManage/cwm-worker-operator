import time
import traceback
import datetime
import json

import cwm_worker_deployment.deployment

from cwm_worker_operator import config
from cwm_worker_operator import metrics


def init_cache():
    for version in config.CACHE_MINIO_VERSIONS:
        try:
            chart_path = cwm_worker_deployment.deployment.chart_cache_init("cwm-worker-deployment-minio", version, "minio")
            print("Initialized chart cache: {}".format(chart_path), flush=True)
        except Exception:
            traceback.print_exc()
            print("Failed to initialize chart cache for version {}".format(version))


def init_domain_waiting_for_deploy(redis_pool, domain_name, _metrics, namespaces, error_attempt_number=None):
    _metrics.send("domains waiting for init", domain_name=domain_name)
    try:
        volume_config = config.get_cwm_api_volume_config(redis_pool, domain_name, _metrics)
        namespace_name = volume_config["hostname"].replace(".", "--")
        volume_zone = volume_config["zone"]
    except Exception:
        traceback.print_exc()
        print("ERROR! Failed to get volume config (domain={})".format(domain_name))
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG, _metrics, error_attempt_number)
        return
    if volume_zone != config.CWM_ZONE:
        print("ERROR! Invalid volume zone (domain={} volume_zone={} CWM_ZONE={})".format(domain_name, volume_zone, config.CWM_ZONE))
        config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_INVALID_VOLUME_ZONE, _metrics, error_attempt_number)
        return
    if namespace_name in namespaces:
        if namespaces[namespace_name]["volume_config"] != volume_config:
            print("ERROR! Different volume configs for same namespace (domain={} namespace={})".format(domain_name, namespace_name))
            config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_DIFFERENT_VOLUME_CONFIGS, _metrics, error_attempt_number)
            return
        else:
            namespaces[namespace_name]["domain_names"].add(domain_name)
    else:
        namespaces[namespace_name] = {
            "domain_names": {domain_name},
            "volume_config": volume_config
        }
    _metrics.send("domains ready for init", domain_name=domain_name)


def deploy_namespace(redis_pool, namespace_name, namespace_config, _metrics, namespaces_deployed, domains_error_attempt_numbers=None, debug=False):
    _metrics.send("namespaces waiting for deploy", namespace_name=namespace_name)
    volume_config = namespace_config["volume_config"]
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
        cwm_worker_deployment.deployment.deploy(deployment_config)
    except Exception:
        traceback.print_exc()
        print("ERROR! Failed to deploy (namespace={})".format(namespace_name))
        for domain_name in namespace_config["domain_names"]:
            error_attempt_number = domains_error_attempt_numbers[domain_name] if domains_error_attempt_numbers else None
            config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_FAILED_TO_DEPLOY, _metrics, error_attempt_number)
        return
    _metrics.send("namespaces deployed", namespace_name=namespace_name)
    namespaces_deployed.add(namespace_name)


def wait_for_namespaces_deployed(redis_pool, namespaces_deployed, namespaces, _metrics, wait_deployment_ready_max_seconds, domains_error_attempt_numbers=None):
    start_time = datetime.datetime.now()
    namespaces_ready = set()
    while len(namespaces_ready) != len(namespaces_deployed):
        for namespace_name in namespaces_deployed:
            namespace_config = namespaces[namespace_name]
            if namespace_name not in namespaces_ready and cwm_worker_deployment.deployment.is_ready(namespace_name, "minio"):
                namespaces_ready.add(namespace_name)
                for domain_name in namespace_config["domain_names"]:
                    config.set_worker_available(redis_pool, domain_name)
                    config.set_worker_ingress_hostname(redis_pool, domain_name, cwm_worker_deployment.deployment.get_hostname(namespace_name, "minio"))
                    config.del_worker_error(redis_pool, domain_name)
                    config.del_worker_initialize(redis_pool, domain_name)
                    _metrics.send("domain is available", namespace_name=namespace_name, domain_name=domain_name)
        if (datetime.datetime.now() - start_time).total_seconds() > wait_deployment_ready_max_seconds:
            break
        time.sleep(0.1)
    for namespace_name in namespaces_deployed:
        if namespace_name not in namespaces_ready:
            print("ERROR! Timeout waiting for deployment (namespace={})".format(namespace_name))
            for domain_name in namespaces[namespace_name]["domain_names"]:
                error_attempt_number = domains_error_attempt_numbers[domain_name] if domains_error_attempt_numbers else None
                config.set_worker_error(redis_pool, domain_name, config.WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT, _metrics, error_attempt_number)


def start(once=False):
    redis_pool = config.get_redis_pool()
    deployer_metrics = metrics.Metrics(config.METRICS_GROUP_DEPLOYER_PATH_SUFFIX)
    while True:
        deployer_metrics.send("iterations started", debug_verbosity=8)
        domains_waiting_for_initialization = config.get_worker_domains_waiting_for_initlization(redis_pool)
        namespaces = {}
        for domain_name in domains_waiting_for_initialization:
            init_domain_waiting_for_deploy(redis_pool, domain_name, deployer_metrics, namespaces)
        namespaces_deployed = set()
        for namespace_name, namespace_config in namespaces.items():
            deploy_namespace(redis_pool, namespace_name, namespace_config, deployer_metrics, namespaces_deployed)
        wait_for_namespaces_deployed(redis_pool, namespaces_deployed, namespaces, deployer_metrics, config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS)
        deployer_metrics.send("iterations ended", debug_verbosity=8)
        if once:
            deployer_metrics.save(force=True)
            break
        deployer_metrics.save()
        time.sleep(config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)


def debug_deployment(domain_name):
    init_cache()
    redis_pool = config.get_redis_pool()
    deployer_metrics = metrics.Metrics(config.METRICS_GROUP_DEPLOYER_PATH_SUFFIX, is_dummy=True)
    namespaces = {}
    init_domain_waiting_for_deploy(redis_pool, domain_name, deployer_metrics, namespaces)
    namespaces_deployed = set()
    for namespace_name, namespace_config in namespaces.items():
        print("Deploying namespace {}".format(namespace_name), flush=True)
        namespace_config["domain_names"] = list(namespace_config["domain_names"])
        print(json.dumps(namespace_config), flush=True)
        deploy_namespace(redis_pool, namespace_name, namespace_config, deployer_metrics, namespaces_deployed, debug=True)
    wait_for_namespaces_deployed(redis_pool, namespaces_deployed, namespaces, deployer_metrics, config.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS)
