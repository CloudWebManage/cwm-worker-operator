"""
Deploys workers
"""
import sys
import json
import traceback
import subprocess
import urllib.parse

from cwm_worker_operator import config, common
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import domains_config as domains_config_module
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.deployment_flow_manager import DeployerDeploymentFlowManager
from cwm_worker_operator.multiprocessor import Multiprocessor


def initialize_deploy_worker_args(domains_config, deployer_metrics, deployments_manager, flow_manager, extra_minio_extra_configs):
    if domains_config is None:
        domains_config = domains_config_module.DomainsConfig()
    # due to the parallel processing we can't send metrics
    # if deployer_metrics is None:
    #     deployer_metrics = metrics.DeployerMetrics()
    deployer_metrics = None
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    if flow_manager is None:
        flow_manager = DeployerDeploymentFlowManager(domains_config)
    if extra_minio_extra_configs and not isinstance(extra_minio_extra_configs, dict):
        extra_minio_extra_configs = json.loads(extra_minio_extra_configs)
    return domains_config, deployer_metrics, deployments_manager, flow_manager, extra_minio_extra_configs


def deploy_worker(domains_config=None, deployer_metrics=None, deployments_manager=None, worker_id=None, debug=False,
                  extra_minio_extra_configs=None, dry_run=None, flow_manager=None,
                  preprocess_result=None, force=False):
    domains_config, deployer_metrics, deployments_manager, flow_manager, extra_minio_extra_configs = initialize_deploy_worker_args(
        domains_config, deployer_metrics, deployments_manager, flow_manager, extra_minio_extra_configs)
    start_time = domains_config.get_worker_ready_for_deployment_start_time(worker_id)
    log_kwargs = {"worker_id": worker_id, "start_time": start_time}
    try:
        if preprocess_result is None:
            preprocess_result = deploy_worker_preprocess(
                worker_id, domains_config, deployer_metrics, flow_manager, dry_run, debug, extra_minio_extra_configs,
                deployments_manager, force=force
            )
        namespace_name, deployment_config, extra_objects, deploy_preprocess_result = preprocess_result
        if deployment_config:
            logs.debug("initializing deployment", debug_verbosity=9, **log_kwargs)
            deployments_manager.init(deployment_config)
            logs.debug("initialized deployment", debug_verbosity=9, **log_kwargs)
            # if config.DEPLOYER_USE_EXTERNAL_SERVICE:
            #     deployments_manager.deploy_external_service(deployment_config)
            #     logs.debug("deployed external service", debug_verbosity=4, **log_kwargs)
            # if config.DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS and len(extra_objects) > 0:
            #     deployments_manager.deploy_extra_objects(deployment_config, extra_objects)
            #     logs.debug("deployed external extra objects", debug_verbosity=4, **log_kwargs)
            if debug or config.DEPLOYER_WITH_HELM_DRY_RUN or dry_run:
                print(deployments_manager.deploy(
                    deployment_config, dry_run=True, with_init=False,
                    preprocess_result=deploy_preprocess_result
                ))
                logs.debug("deployed dry run", debug_verbosity=4, **log_kwargs)
            if dry_run:
                print('dry_run: not deploying')
            else:
                try:
                    deploy_output = deployments_manager.deploy(
                        deployment_config, with_init=False, preprocess_result=deploy_preprocess_result
                    )
                except Exception:
                    if debug or (config.DEBUG and config.DEBUG_VERBOSITY >= 3):
                        traceback.print_exc(file=sys.stdout)
                        print("ERROR! Failed to deploy (namespace={})".format(namespace_name), flush=True)
                    attempt_number = domains_config.get_worker_deployment_attempt_number(worker_id)
                    if attempt_number >= config.DEPLOYER_MAX_ATTEMPT_NUMBERS:
                        flow_manager.set_worker_error(worker_id, domains_config.WORKER_ERROR_FAILED_TO_DEPLOY)
                        print("{} failed attempts, giving up".format(attempt_number))
                    else:
                        flow_manager.wait_retry_deployment(worker_id)
                        print("Will retry ({} / {} attempts)".format(attempt_number+1, config.DEPLOYER_MAX_ATTEMPT_NUMBERS))
                    # deployer_metrics.deploy_failed(worker_id, start_time)
                    logs.debug_info("failed to deploy", **log_kwargs)
                    return True
                logs.debug("deployed", debug_verbosity=4, **log_kwargs)
                if config.DEBUG and config.DEBUG_VERBOSITY >= 9:
                    print(deploy_output, flush=True)
                # deployer_metrics.deploy_success(worker_id, start_time)
                flow_manager.set_worker_waiting_for_deployment(worker_id)
                logs.debug_info("success", **log_kwargs)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        # deployer_metrics.exception(worker_id, start_time)
    return True


def deploy_worker_preprocess(worker_id: str, domains_config: domains_config_module.DomainsConfig,
                             deployer_metrics, flow_manager: DeployerDeploymentFlowManager,
                             dry_run: bool, debug: bool, extra_minio_extra_configs,
                             deployments_manager: DeploymentsManager, force=False):
    domains_config, deployer_metrics, deployments_manager, flow_manager, extra_minio_extra_configs = initialize_deploy_worker_args(
        domains_config, deployer_metrics, deployments_manager, flow_manager, extra_minio_extra_configs)
    start_time = domains_config.get_worker_ready_for_deployment_start_time(worker_id)
    log_kwargs = {"worker_id": worker_id, "start_time": start_time}
    logs.debug("Start deploy_worker", debug_verbosity=4, **log_kwargs)
    try:
        volume_config, namespace_name = domains_config.get_volume_config_namespace_from_worker_id(
            deployer_metrics, worker_id)
        if not namespace_name:
            # deployer_metrics.failed_to_get_volume_config(worker_id, start_time)
            logs.debug_info("Failed to get volume config", **log_kwargs)
            flow_manager.set_worker_error(worker_id, domains_config.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
            return None, None, None, None
        if not force and not flow_manager.is_valid_worker_hostnames_for_deployment(worker_id, volume_config.hostnames):
            if not dry_run or not debug:
                logs.debug_info("flow_manager says that worker_hostnames are not valid for deployment, sorry", **log_kwargs)
                return namespace_name, None, None, None
        logs.debug("Got volume config", debug_verbosity=4, **log_kwargs)
        deployment_config, extra_objects = get_deployment_config(debug, domains_config, extra_minio_extra_configs, namespace_name, volume_config)
        deploy_preprocess_result = deployments_manager.deploy_preprocess_specs({0: deployment_config})[0]
        return namespace_name, deployment_config, extra_objects, deploy_preprocess_result
    except Exception as e:
        logs.debug_info("exception: {}".format(e), **log_kwargs)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        # deployer_metrics.exception(worker_id, start_time)
        return None, None, None, None


def get_deployment_config(debug, domains_config, extra_minio_extra_configs, namespace_name, volume_config):
    minio_extra_configs = common.dicts_merge(
        {'browser': volume_config.browser_enabled},
        config.MINIO_EXTRA_CONFIG,
        volume_config.minio_extra_configs,
        extra_minio_extra_configs if extra_minio_extra_configs else {}
    )
    cwm_worker_deployment_extra_configs = common.dicts_merge(
        config.CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG,
        volume_config.cwm_worker_deployment_extra_configs
    )
    extra_objects = [
        *config.CWM_WORKER_EXTRA_OBJECTS,
        *volume_config.cwm_worker_extra_objects
    ]
    minio = {
        'domain_name': volume_config.hostnames[0] if len(volume_config.hostnames) else ''
    }
    if volume_config.client_id and volume_config.secret:
        minio["access_key"] = volume_config.client_id
        minio["secret_key"] = volume_config.secret
    if config.DEPLOYER_USE_EXTERNAL_SERVICE:
        minio["service"] = {
            "enabled": False
        }
    minio["MINIO_GATEWAY_DEPLOYMENT_ID"] = namespace_name
    minio["metricsLogger"] = common.dicts_merge(
        {
            "withRedis": False,
            "REDIS_HOST": config.METRICS_REDIS_HOST,
            "REDIS_PORT": config.METRICS_REDIS_PORT,
            "REDIS_POOL_MAX_CONNECTIONS": config.METRICS_REDIS_POOL_MAX_CONNECTIONS,
            "REDIS_POOL_TIMEOUT": config.METRICS_REDIS_POOL_TIMEOUT,
            "REDIS_DB": config.METRICS_REDIS_DB,
            "REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION": domains_config.keys.deployment_last_action.key_prefix,
            "UPDATE_GRACE_PERIOD_SECONDS": config.LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS,
            "DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS": config.METRICS_LOGGER_DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS,
            "REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC": domains_config.keys.deployment_api_metric.key_prefix,
            'LOGS_FLUSH_INTERVAL': '300s',
            # this is required for the current usage of logging to self
            # TODO: when we add support for more logging options need to fix this
            'S3_CHECK_APIKEY_ON_START': 'false',
            'S3_CHECK_BUCKET': 'false'
        },
        minio_extra_configs.pop('metricsLogger', {})
    )
    minio['cache'] = common.dicts_merge(
        {
            "enabled": True,
            "drives": "/cache",
            "exclude": "",  # ','.join(['*.{}'.format(ext) for ext in volume_config.cache_exclude_extensions]),
            "quota": 80,
            "after": 3,
            "watermark_low": 70,
            "watermark_high": 90,
        },
        minio_extra_configs.pop('cache', {})
    )
    nginx_primary_hostname = None
    nginx_secondary_hostnames = []
    for i, hostname in enumerate(volume_config.hostnames):
        nginx_hostname = {'id': i, 'name': hostname}
        if hostname in volume_config.hostname_certs:
            nginx_hostname.update(fullchain=volume_config.hostname_certs[hostname]['fullchain'],
                                  chain=volume_config.hostname_certs[hostname]['chain'],
                                  privkey=volume_config.hostname_certs[hostname]['privkey'])
        if hostname in volume_config.hostname_challenges:
            nginx_hostname.update(cc_token=volume_config.hostname_challenges[hostname]['token'],
                                  cc_payload=volume_config.hostname_challenges[hostname]['payload'])
        if not nginx_primary_hostname and volume_config.primary_hostname and nginx_hostname['name'].lower() == volume_config.primary_hostname.lower():
            nginx_primary_hostname = nginx_hostname
        else:
            nginx_secondary_hostnames.append(nginx_hostname)
    minio['nginx'] = common.dicts_merge(
        {
            'dhparam_key': config.DHPARAM_KEY,
            'hostnames': [*([nginx_primary_hostname] if nginx_primary_hostname else []), *nginx_secondary_hostnames],
            'CDN_CACHE_ENABLE': volume_config.cache_enabled,
            'CDN_CACHE_NOCACHE_REGEX': '\\.({})$'.format('|'.join(volume_config.cache_exclude_extensions)) if len(volume_config.cache_exclude_extensions) > 0 else '',
            'CDN_CACHE_PROXY_CACHE_VALID_200': '{}m'.format(volume_config.cache_expiry_minutes),
            'CDN_CACHE_PROXY_INACTIVE': '{}m'.format(volume_config.cache_expiry_minutes + 1),
            'DISABLE_HTTP': 'http' not in volume_config.protocols_enabled,
            'DISABLE_HTTPS': 'https' not in volume_config.protocols_enabled,
        },
        minio_extra_configs.pop('nginx', {})
    )
    if volume_config.gateway:
        if isinstance(volume_config.gateway, domains_config_module.VolumeConfigGatewayTypeS3):
            minio['INSTANCE_TYPE'] = 'gateway_s3'
            if volume_config.gateway.url:
                minio['GATEWAY_ARGS'] = volume_config.gateway.url
                try:
                    parse_result = urllib.parse.urlparse(volume_config.gateway.url)
                    port = parse_result.port or (80 if parse_result.scheme == 'http' else 443)
                except:
                    port = 443
                minio['gatewayNetworkPolicyExtraEgressPorts'] = [port]
            minio['AWS_ACCESS_KEY_ID'] = volume_config.gateway.access_key
            minio['AWS_SECRET_ACCESS_KEY'] = volume_config.gateway.secret_access_key
        elif isinstance(volume_config.gateway, domains_config_module.VolumeConfigGatewayTypeAzure):
            minio['INSTANCE_TYPE'] = 'gateway_azure'
            minio['AZURE_STORAGE_ACCOUNT_NAME'] = volume_config.gateway.account_name
            minio['AZURE_STORAGE_ACCOUNT_KEY'] = volume_config.gateway.account_key
        elif isinstance(volume_config.gateway, domains_config_module.VolumeConfigGatewayTypeGoogle):
            minio['INSTANCE_TYPE'] = 'gateway_gcs'
            minio['GATEWAY_ARGS'] = volume_config.gateway.project_id
            minio['GOOGLE_APPLICATION_CREDENTIALS'] = volume_config.gateway.credentials
    deployment_config_json = json.dumps({
        "cwm-worker-deployment": common.dicts_merge(
            {
                "type": "minio",
                "namespace": namespace_name,
            },
            cwm_worker_deployment_extra_configs
        ),
        "minio": common.dicts_merge(minio, minio_extra_configs),
        "extraObjects": extra_objects
    }).replace("__NAMESPACE_NAME__", namespace_name)
    if debug or config.DEBUG_VERBOSITY >= 10 or config.DEPLOYER_WITH_HELM_DRY_RUN:
        print('---- deployment_config_json ----')
        print(deployment_config_json, flush=True)
        print('--------------------------------')
    deployment_config = json.loads(deployment_config_json)
    if config.DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS:
        if debug:
            print('DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS is true - removing extraObjects from deployment config')
        extra_objects = deployment_config.pop('extraObjects')
        deployment_config['extraObjects'] = []
    return deployment_config, extra_objects


class DeployerMultiprocessor(Multiprocessor):

    def _run_async(self, worker_id, extra_minio_extra_configs, domains_config, metrics, deployments_manager,
                   flow_manager, preprocess_result):
        cmd = ['cwm-worker-operator', 'deployer', 'deploy_worker', '--worker-id', worker_id]
        if extra_minio_extra_configs:
            cmd += ['--extra-minio-extra-configs', json.dumps(extra_minio_extra_configs)]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run_sync(self, worker_id, extra_minio_extra_configs, domains_config, metrics, deployments_manager,
                  flow_manager, preprocess_result):
        deploy_worker(domains_config, metrics, deployments_manager, worker_id,
                      extra_minio_extra_configs=extra_minio_extra_configs,
                      flow_manager=flow_manager, preprocess_result=preprocess_result)

    def _get_process_key(self, worker_id, *args, **kwargs):
        return worker_id


def run_single_iteration(domains_config: domains_config_module.DomainsConfig, metrics, deployments_manager, extra_minio_extra_configs=None, is_async=True, **_):
    multiprocessor = DeployerMultiprocessor(config.DEPLOYER_MAX_PARALLEL_DEPLOY_PROCESSES if is_async else 1)
    flow_manager = DeployerDeploymentFlowManager(domains_config)
    preprocess_results = {}
    for worker_id in flow_manager.iterate_worker_ids_ready_for_deployment():
        preprocess_results[worker_id] = deploy_worker_preprocess(
            worker_id, domains_config, metrics, flow_manager, False, False, extra_minio_extra_configs, deployments_manager)
    for worker_id, preprocess_result in preprocess_results.items():
        multiprocessor.process(worker_id, extra_minio_extra_configs, domains_config, metrics, deployments_manager,
                               flow_manager, preprocess_result)
    multiprocessor.finalize()


def start_daemon(once=False, with_prometheus=True, deployer_metrics=None, domains_config=None, extra_minio_extra_configs=None):
    deployments_manager = DeploymentsManager()
    # deployments_manager.init_cache()
    Daemon(
        name='deployer',
        sleep_time_between_iterations_seconds=config.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.DeployerMetrics,
        domains_config=domains_config,
        metrics=deployer_metrics,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_DEPLOYER,
        run_single_iteration_extra_kwargs={'extra_minio_extra_configs': extra_minio_extra_configs},
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
