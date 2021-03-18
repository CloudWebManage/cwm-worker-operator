import sys
import time
import json
import traceback

import prometheus_client

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import domains_config as domains_config_module


def deploy_worker(domains_config, deployer_metrics, deployments_manager, domain_name, debug=False, extra_minio_extra_configs=None):
    start_time = domains_config.get_worker_ready_for_deployment_start_time(domain_name)
    log_kwargs = {"domain_name": domain_name, "start_time": start_time}
    logs.debug("Start deploy_worker", debug_verbosity=4, **log_kwargs)
    try:
        volume_config, namespace_name = domains_config.get_volume_config_namespace_from_domain(deployer_metrics, domain_name)
        if not namespace_name:
            deployer_metrics.failed_to_get_volume_config(domain_name, start_time)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            return
        logs.debug("Got volume config", debug_verbosity=4, **log_kwargs)
        protocol = volume_config.get("protocol", "http")
        certificate_key = volume_config.get("certificate_key")
        certificate_key = "\n".join(certificate_key) if certificate_key else None
        certificate_pem = volume_config.get("certificate_pem")
        certificate_pem = "\n".join(certificate_pem) if certificate_pem else None
        client_id = volume_config.get("client_id")
        secret = volume_config.get("secret")
        minio_extra_configs = {
            **config.MINIO_EXTRA_CONFIG,
            **volume_config.get("minio_extra_configs", {}),
            **(extra_minio_extra_configs if extra_minio_extra_configs else {})
        }
        cwm_worker_deployment_extra_configs = {
            **config.CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG,
            **volume_config.get("cwm_worker_deployment_extra_configs", {})
        }
        extra_objects = [
            *config.CWM_WORKER_EXTRA_OBJECTS,
            *volume_config.get("cwm_worker_extra_objects", [])
        ]
        minio = {}
        if config.PULL_SECRET:
            minio['createPullSecret'] = config.PULL_SECRET
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
        if config.DEPLOYER_USE_EXTERNAL_SERVICE:
            minio["service"] = {
                "enabled": False
            }
        minio["MINIO_GATEWAY_DEPLOYMENT_ID_http"] = 'http'
        minio["MINIO_GATEWAY_DEPLOYMENT_ID_https"] = 'https'
        minio["metricsLogger"] = {
            "withRedis": False,
            "REDIS_HOST": config.REDIS_HOST,
            "REDIS_PORT": config.REDIS_PORT,
            "REDIS_POOL_MAX_CONNECTIONS": config.REDIS_POOL_MAX_CONNECTIONS,
            "REDIS_POOL_TIMEOUT": config.REDIS_POOL_TIMEOUT,
            "REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION": domains_config_module.REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION,
            "UPDATE_GRACE_PERIOD_SECONDS": config.LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS,
            "DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS": config.METRICS_LOGGER_DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS,
            "REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC": domains_config_module.REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC,
            **minio_extra_configs.pop('metricsLogger', {})
        }
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
        if config.DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS:
            extra_objects = deployment_config.pop('extraObjects')
            deployment_config['extraObjects'] = []
        logs.debug("initializing deployment", debug_verbosity=4, **log_kwargs)
        deployments_manager.init(deployment_config)
        logs.debug("initialized deployment", debug_verbosity=4, **log_kwargs)
        if config.DEPLOYER_USE_EXTERNAL_SERVICE:
            deployments_manager.deploy_external_service(deployment_config)
            logs.debug("deployed external service", debug_verbosity=4, **log_kwargs)
        if config.DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS and len(extra_objects) > 0:
            deployments_manager.deploy_extra_objects(deployment_config, extra_objects)
            logs.debug("deployed external extra objects", debug_verbosity=4, **log_kwargs)
        if debug:
            deployments_manager.deploy(deployment_config, dry_run=True, with_init=False)
            logs.debug("deployed dry run", debug_verbosity=4, **log_kwargs)
        try:
            deploy_output = deployments_manager.deploy(deployment_config, with_init=False)
        except Exception:
            if debug or (config.DEBUG and config.DEBUG_VERBOSITY >= 3):
                traceback.print_exc(file=sys.stdout)
                print("ERROR! Failed to deploy (namespace={})".format(namespace_name), flush=True)
            domains_config.set_worker_error(domain_name, domains_config.WORKER_ERROR_FAILED_TO_DEPLOY)
            deployer_metrics.deploy_failed(domain_name, start_time)
            logs.debug_info("failed to deploy", **log_kwargs)
            return
        logs.debug("deployed", debug_verbosity=4, **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY > 5:
            print(deploy_output, flush=True)
        deployer_metrics.deploy_success(domain_name, start_time)
        domains_config.set_worker_waiting_for_deployment(domain_name)
        logs.debug_info("success", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        deployer_metrics.exception(domain_name, start_time)


def run_single_iteration(domains_config, deployer_metrics, deployments_manager, extra_minio_extra_configs=None):
    domain_names_waiting_for_deployment_complete = domains_config.get_worker_domains_waiting_for_deployment_complete()
    for domain_name in domains_config.get_worker_domains_ready_for_deployment():
        if domain_name not in domain_names_waiting_for_deployment_complete:
            deploy_worker(domains_config, deployer_metrics, deployments_manager, domain_name, extra_minio_extra_configs=extra_minio_extra_configs)


def start_daemon(once=False, with_prometheus=True, deployer_metrics=None, domains_config=None, extra_minio_extra_configs=None):
    if with_prometheus:
        prometheus_client.start_http_server(config.PROMETHEUS_METRICS_PORT_DEPLOYER)
    if not deployer_metrics:
        deployer_metrics = metrics.DeployerMetrics()
    if not domains_config:
        domains_config = DomainsConfig()
    deployments_manager = DeploymentsManager()
    deployments_manager.init_cache()
    while True:
        run_single_iteration(domains_config, deployer_metrics, deployments_manager, extra_minio_extra_configs=extra_minio_extra_configs)
        if once:
            break
        time.sleep(config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
