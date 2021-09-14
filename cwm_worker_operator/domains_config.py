import json
import redis
import traceback
from copy import deepcopy
from contextlib import contextmanager

from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator import cwm_api_manager


class DomainsConfigKey:

    def __init__(self, redis_pool_name, domains_config, **extra_kwargs):
        assert redis_pool_name in ['ingress', 'internal', 'metrics']
        self.redis_pool_name = redis_pool_name
        self.domains_config = domains_config
        for k, v in extra_kwargs.items():
            setattr(self, k, v)

    @contextmanager
    def get_redis(self):
        with getattr(self.domains_config, 'get_{}_redis'.format(self.redis_pool_name))() as r:
            yield r

    def get(self, *args):
        with self.get_redis() as r:
            return r.get(self._(*args))

    def exists(self, *args):
        with self.get_redis() as r:
            return r.exists(self._(*args))

    def delete(self, *args):
        with self.get_redis() as r:
            r.delete(self._(*args))

class DomainsConfigKeyPrefix(DomainsConfigKey):

    def __init__(self, key_prefix, redis_pool_name, domains_config, **extra_kwargs):
        self.key_prefix = key_prefix
        super(DomainsConfigKeyPrefix, self).__init__(redis_pool_name, domains_config, **extra_kwargs)

    def _(self, param):
        return '{}:{}'.format(self.key_prefix, param)

    def iterate_prefix_key_suffixes(self):
        with self.get_redis() as r:
            for key in r.keys("{}:*".format(self.key_prefix)):
                yield key.decode().replace('{}:'.format(self.key_prefix), '')

    def set(self, param, value):
        with self.get_redis() as r:
            r.set(self._(param), value)


class DomainsConfigKeyPrefixInt(DomainsConfigKeyPrefix):

    def set(self, param, value):
        value = int(value)
        super(DomainsConfigKeyPrefixInt, self).set(param, value)

    def get(self, param):
        val = super(DomainsConfigKeyPrefixInt, self).get(param)
        return 0 if not val else int(val)

    def increment(self, param):
        with self.get_redis() as r:
            return int(r.incr(self._(param)))


class DomainsConfigKeyTemplate(DomainsConfigKey):

    def __init__(self, key_template, redis_pool_name, domains_config, **extra_kwargs):
        self.key_template = key_template
        super(DomainsConfigKeyTemplate, self).__init__(redis_pool_name, domains_config, **extra_kwargs)

    def _(self, param):
        return self.key_template.format(param)

    def set(self, param, value):
        with self.get_redis() as r:
            r.set(self._(param), value)


class DomainsConfigKeyStatic(DomainsConfigKey):

    def __init__(self, key, redis_pool_name, domains_config, **extra_kwargs):
        self.key = key
        super(DomainsConfigKeyStatic, self).__init__(redis_pool_name, domains_config, **extra_kwargs)

    def _(self):
        return self.key
    
    def set(self, value):
        with self.get_redis() as r:
            r.set(self._(), value)


class DomainsConfigKeys:

    def __init__(self, domains_config=None):
        self.domains_config = domains_config

        # ingress_redis - keys shared with cwm-worker-ingress
        self.hostname_initialize = DomainsConfigKeyPrefix("hostname:initialize", 'ingress', domains_config, keys_summary_param='hostname')
        self.hostname_available = DomainsConfigKeyPrefix("hostname:available", 'ingress', domains_config, keys_summary_param='hostname')
        self.hostname_ingress_hostname = DomainsConfigKeyTemplate("hostname:ingress:hostname:{}", 'ingress', domains_config, keys_summary_param='hostname')
        self.hostname_error = DomainsConfigKeyPrefix("hostname:error", 'ingress', domains_config, keys_summary_param='hostname')
        self.node_healthy = DomainsConfigKeyPrefix("node:healthy", 'ingress', domains_config, keys_summary_param='node')

        # internal_redis - keys used internally only by cwm-worker-operator
        self.hostname_error_attempt_number = DomainsConfigKeyTemplate("hostname:error_attempt_number:{}", 'internal', domains_config, keys_summary_param='hostname')
        self.volume_config = DomainsConfigKeyPrefix("worker:volume:config", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_ready_for_deployment = DomainsConfigKeyPrefix("worker:opstatus:ready_for_deployment", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_deployment_error_attempt = DomainsConfigKeyPrefixInt("worker:opstatus:deployment_error_attempt", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_waiting_for_deployment_complete = DomainsConfigKeyPrefix("worker:opstatus:waiting_for_deployment", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_force_update = DomainsConfigKeyPrefix("worker:force_update", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_force_delete = DomainsConfigKeyPrefix("worker:force_delete", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_aggregated_metrics = DomainsConfigKeyPrefix("worker:aggregated-metrics", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_aggregated_metrics_last_sent_update = DomainsConfigKeyPrefix("worker:aggregated-metrics-last-sent-update", 'internal', domains_config, keys_summary_param='worker_id')
        self.worker_total_used_bytes = DomainsConfigKeyPrefix("worker:total-used-bytes", 'internal', domains_config, keys_summary_param='worker_id')
        self.alerts = DomainsConfigKeyStatic("alerts", 'internal', domains_config)
        self.worker_last_clear_cache = DomainsConfigKeyPrefix("worker:last_clear_cache", 'internal', domains_config, keys_summary_param='worker_id')
        self.updater_last_cwm_api_update = DomainsConfigKeyStatic("updater_last_cwm_api_update", 'internal', domains_config)

        # metrics_redis - keys shared with deployments to get metrics
        self.deployment_last_action = DomainsConfigKeyPrefix("deploymentid:last_action", 'metrics', domains_config, keys_summary_param='namespace_name')
        self.deployment_api_metric = DomainsConfigKeyPrefix("deploymentid:minio-metrics", 'metrics', domains_config, keys_summary_param='namespace_name')


class VolumeConfigGatewayTypeS3:

    def __init__(self, url, access_key, secret_access_key):
        self.url = url
        self.access_key = access_key
        self.secret_access_key = secret_access_key


class VolumeConfigGatewayTypeGoogle:

    def __init__(self, project_id, credentials):
        self.project_id = project_id
        self.credentials = credentials


class VolumeConfigGatewayTypeAzure:

    def __init__(self, account_name, account_key):
        self.account_name = account_name
        self.account_key = account_key


class VolumeConfig:
    GATEWAY_TYPE_S3 = 's3'

    def __init__(self, data, domains_config, request_hostname=None, is_data_from_cache=False, request_worker_id=None):
        request_data = deepcopy(data)
        self.id = data.get('instanceId')
        self._error = data.get('__error')
        self._last_update = data.get('__last_update')
        self.zone = data.get('zone')
        self.hostnames = []
        self.hostname_certs = {}
        self.hostname_challenges = {}
        minio_extra_configs = data.get('minio_extra_configs', {})
        self.protocols_enabled = set()
        for protocol in minio_extra_configs.pop('protocols-enabled', ['http', 'https']):
            if protocol.lower() in ['http', 'https']:
                self.protocols_enabled.add(protocol.lower())
        self.zone_hostname, self.geo_hostname, self.root_hostname = None, None, None
        if len(self.protocols_enabled) > 0:
            for hostname in minio_extra_configs.pop('hostnames', []):
                self.hostnames.append(hostname['hostname'])
                if not self.zone_hostname and self.zone and hostname['hostname'].lower() == '{}.{}.{}'.format(self.id, self.zone.lower(), config.AWS_ROUTE53_HOSTEDZONE_DOMAIN):
                    self.zone_hostname = hostname['hostname']
                if not self.geo_hostname and hostname['hostname'].lower() == '{}.geo.{}'.format(self.id, config.AWS_ROUTE53_HOSTEDZONE_DOMAIN):
                    self.geo_hostname = hostname['hostname']
                if not self.root_hostname and hostname['hostname'].lower() == '{}.{}'.format(self.id, config.AWS_ROUTE53_HOSTEDZONE_DOMAIN):
                    self.root_hostname = hostname['hostname']
                if 'https' in self.protocols_enabled:
                    if hostname.get('privateKey') and hostname.get('fullChain'):
                        self.hostname_certs[hostname['hostname']] = {
                            'privkey': "\n".join(hostname['privateKey']),
                            'fullchain': "\n".join(hostname['fullChain']),
                            'chain': "\n".join(hostname['chain']) if hostname.get('chain') else '',
                        }
                    elif hostname.get('certificate_key') and hostname.get('certificate_pem'):
                        self.hostname_certs[hostname['hostname']] = {
                            'privkey': "\n".join(hostname['certificate_key']),
                            'fullchain': "\n".join(hostname['certificate_pem']),
                            'chain': ""
                        }
                if hostname.get('token') and hostname.get('payload'):
                    self.hostname_challenges[hostname['hostname']] = {
                        'token': hostname['token'],
                        'payload': hostname['payload']
                    }

        self.primary_hostname = self.zone_hostname or self.geo_hostname or self.root_hostname
        self.client_id = data.get("client_id")
        self.secret = data.get("secret")
        self.cache_enabled = bool(data.get('cache'))
        try:
            self.cache_exclude_extensions = [ext.strip() for ext in data.get('cache-exclude', '').split('|') if ext.strip()]
        except:
            self.cache_exclude_extensions = []
        try:
            self.cache_expiry_minutes = int(data.get('cache-expiry') or 2)
        except:
            self.cache_expiry_minutes = 2
        self.clear_cache = None
        if data.get('clear-cache'):
            try:
                self.clear_cache = common.strptime(data['clear-cache'], '%Y-%m-%d %H:%M:%S')
            except:
                pass
        self.geo_cache_enabled = bool(data.get('geo-cache'))
        self.browser_enabled = bool(data.get('minio-browser', True))
        self.minio_extra_configs = minio_extra_configs
        self.cwm_worker_deployment_extra_configs = data.get("cwm_worker_deployment_extra_configs", {})
        self.cwm_worker_extra_objects = data.get("cwm_worker_extra_objects", [])
        self.disable_force_delete = data.get("disable_force_delete")
        self.disable_force_update = data.get("disable_force_update")
        self.is_valid_zone_for_cluster = bool(self.zone and (self.zone.lower() == config.CWM_ZONE.lower() or self.zone.lower() in map(str.lower, config.CWM_ADDITIONAL_ZONES)))
        self.gateway = self._original_gateway = self.get_volume_config_gateway(data, domains_config, is_data_from_cache)
        if self.gateway:
            self.is_valid_zone_for_cluster = True
        self.gateway_updated_for_request_hostname = None
        self.update_for_hostname(request_hostname or data.get('__request_hostname'))
        if domains_config and request_worker_id and (not is_data_from_cache or (request_hostname is not None and data.get('__request_hostname') != request_hostname)):
            request_data['__request_hostname'] = request_hostname
            self._last_update = request_data["__last_update"] = common.now().strftime("%Y%m%dT%H%M%S")
            domains_config.keys.volume_config.set(request_worker_id, json.dumps(request_data))


    def __str__(self):
        res = {}
        for key in dir(self):
            if key.startswith('__') and key.endswith('__'):
                continue
            value = getattr(self, key)
            if callable(value):
                continue
            if key == 'hostname_certs':
                value = '--'
            elif key == 'gateway':
                value = str(value)
            elif key == 'protocols_enabled':
                value = list(value)
            res[key] = value
        try:
            return json.dumps(res)
        except:
            print(res)
            raise

    def update_for_hostname(self, hostname):
        if not self._original_gateway and hostname:
            if not self.is_valid_zone_for_cluster and self.primary_hostname and common.is_hostnames_match(hostname, self.primary_hostname):
                protocol = 'https' if self.hostname_certs.get(self.primary_hostname) and 'https' in self.protocols_enabled else 'http'
                self.gateway = VolumeConfigGatewayTypeS3('{}://{}'.format(protocol, self.primary_hostname), self.client_id, self.secret)
                self.gateway_updated_for_request_hostname = hostname
            elif hostname.lower() in config.MOCK_GATEWAYS.keys():
                self.gateway = VolumeConfigGatewayTypeS3(**config.MOCK_GATEWAYS[hostname.lower()])
                self.gateway_updated_for_request_hostname = hostname
        else:
            self.gateway = self._original_gateway
            self.gateway_updated_for_request_hostname = None

    def get_volume_config_gateway(self, data, domains_config, is_data_from_cache):
        if data.get('type') == 'gateway':
            provider = data.get('provider')
            if provider == 'cwm':
                credentials = data.get('credentials') or {}
                credentials_instanceId = credentials.get('instanceId')
                credentials_clientId = credentials.get('clientId')
                credentials_secret = credentials.get('secret')
                if credentials_instanceId and credentials_clientId and credentials_secret:
                    gateway_volume_config = domains_config.get_cwm_api_volume_config(worker_id=credentials_instanceId, force_update=not is_data_from_cache)
                    if len(gateway_volume_config.hostnames) > 0:
                        gateway_hostname = gateway_volume_config.primary_hostname if gateway_volume_config.primary_hostname else gateway_volume_config.hostnames[0]
                        return VolumeConfigGatewayTypeS3(
                            url='{}://{}'.format('https' if gateway_volume_config.hostname_certs.get(gateway_hostname) and 'https' in gateway_volume_config.protocols_enabled else 'http', gateway_hostname),
                            access_key=credentials_clientId,
                            secret_access_key=credentials_secret
                        )
            elif provider == 'aws':
                credentials = data.get('credentials') or {}
                credentials_accessKey = credentials.get('accessKey')
                credentials_secretKey = credentials.get('secretKey')
                if credentials_accessKey and credentials_secretKey:
                    return VolumeConfigGatewayTypeS3(url=None, access_key=credentials_accessKey, secret_access_key=credentials_secretKey)
            elif provider == 'azure':
                credentials = data.get('credentials') or {}
                credentials_accountName = credentials.get('accountName')
                credentials_accountKey = credentials.get('accountKey')
                if credentials_accountName and credentials_accountKey:
                    return VolumeConfigGatewayTypeAzure(account_name=credentials_accountName, account_key=credentials_accountKey)
            elif provider == 'gcs':
                credentials = data.get('credentials') or {}
                credentials_projectId = credentials.get('projectId')
                credentials_credentialsJson = credentials.get('credentialsJson')
                if credentials_projectId and credentials_credentialsJson:
                    return VolumeConfigGatewayTypeGoogle(project_id=credentials_projectId, credentials=credentials_credentialsJson)
        elif data.get('instanceType') == 'gateway_s3':
            return VolumeConfigGatewayTypeS3(
                url=data.get('gatewayS3Url') or '',
                access_key=data.get('gatewayS3AccessKey') or '',
                secret_access_key=data.get('gatewayS3SecretAccessKey') or ''
            )


class DomainsConfig:
    WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT = "TIMEOUT_WAITING_FOR_DEPLOYMENT"
    WORKER_ERROR_FAILED_TO_DEPLOY = "FAILED_TO_DEPLOY"
    WORKER_ERROR_INVALID_VOLUME_ZONE = "INVALID_VOLUME_ZONE"
    WORKER_ERROR_INVALID_HOSTNAME = "INVALID_HOSTNAME"
    WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG = "FAILED_TO_GET_VOLUME_CONFIG"

    def __init__(self):
        self.keys = DomainsConfigKeys(self)
        self.ingress_redis_pool = self.init_redis(
            'ingress',
            config.INGRESS_REDIS_HOST, config.INGRESS_REDIS_PORT,
            config.INGRESS_REDIS_POOL_MAX_CONNECTIONS, config.INGRESS_REDIS_POOL_TIMEOUT,
            config.INGRESS_REDIS_DB
        )
        self.internal_redis_pool = self.init_redis(
            'internal',
            config.INTERNAL_REDIS_HOST, config.INTERNAL_REDIS_PORT,
            config.INTERNAL_REDIS_POOL_MAX_CONNECTIONS, config.INTERNAL_REDIS_POOL_TIMEOUT,
            config.INTERNAL_REDIS_DB
        )
        self.metrics_redis_pool = self.init_redis(
            'metrics',
            config.METRICS_REDIS_HOST, config.METRICS_REDIS_PORT,
            config.METRICS_REDIS_POOL_MAX_CONNECTIONS, config.METRICS_REDIS_POOL_TIMEOUT,
            config.METRICS_REDIS_DB
        )

    def init_redis(self, type, host, port, pool_max_connections, pool_timeout, db):
        print("{}: host={} port={}".format(type, host, port))
        redis_pool = redis.BlockingConnectionPool(
            max_connections=pool_max_connections, timeout=pool_timeout,
            host=host, port=port, db=db
        )
        r = redis.Redis(connection_pool=redis_pool)
        try:
            assert r.ping()
        finally:
            r.close()
        return redis_pool

    @contextmanager
    def get_redis(self, redis_pool):
        r = redis.Redis(connection_pool=redis_pool)
        try:
            yield r
        finally:
            r.close()

    @contextmanager
    def get_ingress_redis(self):
        with self.get_redis(self.ingress_redis_pool) as r:
            yield r

    @contextmanager
    def get_internal_redis(self):
        with self.get_redis(self.internal_redis_pool) as r:
            yield r

    @contextmanager
    def get_metrics_redis(self):
        with self.get_redis(self.metrics_redis_pool) as r:
            yield r

    def get_worker_ids_ready_for_deployment(self):
        return list(self.keys.worker_ready_for_deployment.iterate_prefix_key_suffixes())

    def get_worker_ids_waiting_for_deployment_complete(self):
        return list(self.keys.worker_waiting_for_deployment_complete.iterate_prefix_key_suffixes())

    def get_hostnames_waiting_for_initlization(self):
        return list(self.keys.hostname_initialize.iterate_prefix_key_suffixes())

    def _cwm_api_volume_config_api_call(self, query_param, query_value):
        if (
            config.DUMMY_TEST_WORKER_ID and config.DUMMY_TEST_HOSTNAME
            and (
                (query_param == 'hostname' and query_value == config.DUMMY_TEST_HOSTNAME)
                or (query_param == 'id' and query_value == config.DUMMY_TEST_WORKER_ID)
            )
        ):
            return {
                'instanceId': config.DUMMY_TEST_WORKER_ID,
                'zone': config.CWM_ZONE,
                'minio_extra_configs': {'hostnames': [{'hostname': config.DUMMY_TEST_HOSTNAME}]},
            }
        else:
            return cwm_api_manager.CwmApiManager().volume_config_api_call(query_param, query_value)

    def get_cwm_api_volume_config(self, metrics=None, force_update=False, hostname=None, worker_id=None) -> VolumeConfig:
        if hostname:
            assert not worker_id
        elif worker_id:
            assert not hostname
        else:
            raise Exception("either hostname or worker_id param is required")
        start_time = common.now()
        if force_update or not worker_id:
            # TODO: support cache for getting volume config based on hostname
            val = None
        else:
            val = self.keys.volume_config.get(worker_id)
        if val is None:
            if hostname:
                query_param = 'hostname'
                query_value = hostname
            else:
                query_param = 'id'
                query_value = worker_id
            try:
                volume_config = self._cwm_api_volume_config_api_call(query_param, query_value)
                is_success = True
            except Exception as e:
                if config.DEBUG and config.DEBUG_VERBOSITY > 5:
                    traceback.print_exc()
                    print("Failed to get volume config for {}={}".format(query_param, query_value))
                volume_config = {"__error": str(e)}
                is_success = False
            if worker_id:
                if not volume_config.get('instanceId') or volume_config['instanceId'] != worker_id:
                    is_success = False
                    volume_config['__error'] = 'mismatched worker_id'
                    volume_config.pop('instanceId', None)
            elif not volume_config.get('instanceId'):
                is_success = False
                volume_config['__error'] = 'missing worker_id'
                volume_config.pop('instanceId', None)
            else:
                worker_id = volume_config['instanceId']
            if metrics:
                if is_success:
                    metrics.cwm_api_volume_config_success_from_api(worker_id or 'missing', start_time)
                else:
                    metrics.cwm_api_volume_config_error_from_api(worker_id or 'missing', start_time)
            return VolumeConfig(volume_config, self, request_hostname=hostname, is_data_from_cache=False, request_worker_id=worker_id)
        else:
            if metrics:
                # success from cache is only possible when we got a worker_id
                # TODO: add support for cache based on hostname
                metrics.cwm_api_volume_config_success_from_cache(worker_id, start_time)
            return VolumeConfig(json.loads(val), self, request_hostname=hostname, is_data_from_cache=True, request_worker_id=worker_id)

    def set_worker_error(self, worker_id, error_msg):
        for hostname in self.iterate_worker_hostnames(worker_id):
            self.keys.hostname_error.set(hostname, error_msg)
        self.del_worker_keys(worker_id, with_error=False, with_volume_config=False)

    def set_worker_error_by_hostname(self, hostname, error_msg):
        self.keys.hostname_error.set(hostname, error_msg)
        self.del_worker_hostname_keys(hostname, with_error=False)
        try:
            self.set_worker_error(self.get_cwm_api_volume_config(hostname=hostname).id, error_msg)
        except:
            pass

    def increment_worker_error_attempt_number(self, hostname):
        attempt_number = self.keys.hostname_error_attempt_number.get(hostname)
        attempt_number = int(attempt_number) if attempt_number else 0
        self.keys.hostname_error_attempt_number.set(hostname, str(attempt_number + 1))
        return attempt_number + 1

    def set_worker_ready_for_deployment(self, worker_id):
        self.keys.worker_ready_for_deployment.set(worker_id, common.now().strftime("%Y%m%dT%H%M%S.%f"))

    def get_worker_ready_for_deployment_start_time(self, worker_id):
        try:
            dt = common.strptime(self.keys.worker_ready_for_deployment.get(worker_id).decode(), "%Y%m%dT%H%M%S.%f")
        except Exception as e:
            logs.debug_info("exception: {}".format(e), worker_id=worker_id)
            if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                traceback.print_exc()
            dt = common.now()
        return dt

    def get_volume_config_namespace_from_worker_id(self, metrics, worker_id):
        volume_config = self.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
        namespace_name = common.get_namespace_name_from_worker_id(volume_config.id) if volume_config.id else None
        return volume_config, namespace_name

    def set_worker_waiting_for_deployment(self, worker_id, wait_for_error=False):
        self.keys.worker_waiting_for_deployment_complete.set(worker_id, 'error' if wait_for_error else '')

    def get_worker_deployment_attempt_number(self, worker_id):
        return self.keys.worker_deployment_error_attempt.get(worker_id)

    def increment_worker_deployment_attempt_number(self, worker_id):
        return self.keys.worker_deployment_error_attempt.increment(worker_id)

    def is_worker_waiting_for_deployment(self, worker_id):
        if self.keys.worker_waiting_for_deployment_complete.exists(worker_id):
            return True
        if self.keys.worker_ready_for_deployment.exists(worker_id):
            return True
        for hostname in self.iterate_worker_hostnames(worker_id):
            if self.keys.hostname_initialize.exists(hostname):
                return True
        return False

    def iterate_worker_hostnames(self, worker_id):
        volume_hostnames = set()
        for hostname in self.get_cwm_api_volume_config(worker_id=worker_id).hostnames:
            volume_hostnames.add(hostname.lower())
            yield hostname
        for request_hostname in self.get_hostnames_waiting_for_initlization():
            if request_hostname.lower() not in volume_hostnames and common.is_hostnames_match_in_list(request_hostname, volume_hostnames):
                yield request_hostname

    def set_worker_available(self, worker_id, ingress_hostname):
        # del_worker_keys deletes the initialize hostname keys which are used to
        # determine the list of hostnames to set available, so we need to keep
        # the list of hostnames in a variable here
        hostnames = list(self.iterate_worker_hostnames(worker_id))
        self.del_worker_keys(worker_id, with_volume_config=False, with_available=False, with_ingress=False)
        for hostname in hostnames:
            self.keys.hostname_available.set(hostname, '')
            self.keys.hostname_ingress_hostname.set(hostname, json.dumps(ingress_hostname))

    def is_worker_available(self, worker_id):
        num_availale_hostnames = 0
        for hostname in self.iterate_worker_hostnames(worker_id):
            if not self.keys.hostname_available.exists(hostname):
                return False
            num_availale_hostnames += 1
        return num_availale_hostnames > 0

    def del_worker_hostname_keys(self, hostname, with_error=True, with_available=True, with_ingress=True):
        self.keys.hostname_initialize.delete(hostname)
        if with_available:
            self.keys.hostname_available.delete(hostname)
        if with_ingress:
            self.keys.hostname_ingress_hostname.delete(hostname)
        if with_error:
            self.keys.hostname_error.delete(hostname)
            self.keys.hostname_error_attempt_number.delete(hostname)

    def del_worker_keys(self, worker_id, with_error=True, with_volume_config=True, with_available=True, with_ingress=True, with_metrics=False):
        try:
            for hostname in self.iterate_worker_hostnames(worker_id):
                self.del_worker_hostname_keys(hostname, with_error=with_error, with_available=with_available, with_ingress=with_ingress)
        except:
            print("Failed to delete worker hostname keys")
            traceback.print_exc()
        self.keys.worker_ready_for_deployment.delete(worker_id)
        self.keys.worker_deployment_error_attempt.delete(worker_id)
        self.keys.worker_waiting_for_deployment_complete.delete(worker_id)
        self.keys.worker_force_update.delete(worker_id)
        self.keys.worker_force_delete.delete(worker_id)
        self.keys.worker_last_clear_cache.delete(worker_id)
        if with_metrics:
            self.keys.worker_aggregated_metrics.delete(worker_id)
            self.keys.worker_aggregated_metrics_last_sent_update.delete(worker_id)
            self.keys.worker_total_used_bytes.delete(worker_id)
            namespace_name = common.get_namespace_name_from_worker_id(worker_id)
            self.keys.deployment_last_action.delete(namespace_name)
            with self.keys.deployment_api_metric.get_redis() as r:
                keys = r.keys(self.keys.deployment_api_metric._('{}:*'.format(namespace_name)))
                if keys:
                    r.delete(*keys)
        if with_volume_config:
            self.keys.volume_config.delete(worker_id)

    def set_worker_force_update(self, worker_id):
        self.keys.worker_force_update.set(worker_id, '')

    def del_worker_force_update(self, worker_id):
        self.keys.worker_force_update.delete(worker_id)

    def set_worker_force_delete(self, worker_id, allow_cancel=False):
        self.keys.worker_force_delete.set(worker_id, "allow_cancel" if allow_cancel else "")

    def del_worker_force_delete(self, worker_id):
        self.keys.worker_force_delete.delete(worker_id)

    def get_worker_force_delete(self, worker_id):
        value = self.keys.worker_force_delete.get(worker_id)
        if value is not None:
            return {'worker_id': worker_id, 'allow_cancel': value == b"allow_cancel"}
        else:
            return None

    def iterate_domains_to_delete(self):
        workers_to_delete = []
        for worker_id in self.keys.worker_force_delete.iterate_prefix_key_suffixes():
            workers_to_delete.append({
                "worker_id": worker_id,
                "allow_cancel": self.keys.worker_force_delete.get(worker_id) == b"allow_cancel"
            })
        return workers_to_delete

    def get_worker_ids_force_update(self):
        return list(self.keys.worker_force_update.iterate_prefix_key_suffixes())

    def get_worker_aggregated_metrics(self, worker_id, clear=False):
        with self.keys.worker_aggregated_metrics.get_redis() as r:
            if clear:
                value = r.getset(self.keys.worker_aggregated_metrics._(worker_id), '')
            else:
                value = r.get(self.keys.worker_aggregated_metrics._(worker_id))
            if value:
                return json.loads(value.decode())
            else:
                return None

    def get_deployment_api_metrics(self, namespace_name):
        with self.keys.deployment_api_metric.get_redis() as r:
            base_key = "{}:".format(self.keys.deployment_api_metric._(namespace_name))
            return {
                key.decode().replace(base_key, ""): r.get(key).decode()
                for key in r.keys(base_key + "*")
            }

    def set_worker_aggregated_metrics(self, worker_id, agg_metrics):
        self.keys.worker_aggregated_metrics.set(worker_id, json.dumps(agg_metrics))

    # returns tuple of datetimes (last_sent_update, last_update)
    # last_sent_update = the time when the last update was sent to cwm api
    # last_update = the time of the last update which was sent
    def get_worker_aggregated_metrics_last_sent_update(self, worker_id):
        value = self.keys.worker_aggregated_metrics_last_sent_update.get(worker_id)
        if value:
            last_sent_update, last_update = value.decode().split(',')
            last_sent_update = common.strptime(last_sent_update, '%Y%m%d%H%M%S')
            last_update = common.strptime(last_update, '%Y%m%d%H%M%S')
            return last_sent_update, last_update
        else:
            return None, None

    def set_worker_aggregated_metrics_last_sent_update(self, worker_id, last_update):
        value = '{},{}'.format(common.now().strftime('%Y%m%d%H%M%S'), last_update.strftime('%Y%m%d%H%M%S'))
        self.keys.worker_aggregated_metrics_last_sent_update.set(worker_id, value)

    def get_deployment_last_action(self, namespace_name):
        latest_value = None
        value = self.keys.deployment_last_action.get(namespace_name)
        if value:
            value = value.decode().split('.')[0].replace('-', '').replace(':', '')
            value = common.strptime(value, "%Y%m%dT%H%M%S")
            if latest_value is None or value > latest_value:
                latest_value = value
        return latest_value if latest_value else None

    def get_key_summary_single_multi_domain(self, r, key_name, key, max_keys_per_summary):
        if isinstance(key, DomainsConfigKeyStatic):
            match = key._()
        else:
            match = key._('*')
        _keys = []
        _total_keys = 0
        for _key in r.scan_iter(match):
            _total_keys += 1
            if len(_keys) < max_keys_per_summary:
                _keys.append(_key.decode())
        return {
            'title': key_name,
            'keys': _keys,
            'total': _total_keys,
            'pool': key.redis_pool_name
        }

    def get_key_summary_single(self, key_name, key, worker_id, max_keys_per_summary, hostname=None):
        with key.get_redis() as r:
            key_summary_param = getattr(key, 'keys_summary_param', None)
            if worker_id or hostname:
                if key_summary_param in ['namespace_name', 'worker_id'] and worker_id:
                    _key = key._(common.get_namespace_name_from_worker_id(worker_id) if key_summary_param == 'namespace_name' else worker_id)
                elif key_summary_param == 'hostname' and hostname:
                    _key = key._(hostname)
                else:
                    _key = None
                if _key:
                    value = r.get(_key)
                    if value:
                        value = value.decode()
                    return {
                        'title': key_name,
                        'keys': ['{} = {}'.format(_key, value)],
                        'total': 1 if value else 0,
                        'pool': key.redis_pool_name
                    }
                else:
                    return None
            else:
                return self.get_key_summary_single_multi_domain(r, key_name, key, max_keys_per_summary)


    def get_key_summary_prefix_subkeys(self, key_name, key, worker_id, max_keys_per_summary, hostname=None):
        with key.get_redis() as r:
            key_summary_param = getattr(key, 'keys_summary_param', None)
            if worker_id or hostname:
                if key_summary_param in ['namespace_name', 'worker_id'] and worker_id:
                    _key = key._(common.get_namespace_name_from_worker_id(worker_id) if key_summary_param == 'namespace_name' else worker_id)
                elif key_summary_param == 'hostname' and hostname:
                    _key = key._(hostname)
                else:
                    _key = None
                if _key:
                    match = '{}:*'.format(_key)
                    _keys = []
                    _total_keys = 0
                    for _key in r.scan_iter(match):
                        _total_keys += 1
                        if len(_keys) < max_keys_per_summary*3:
                            _keys.append('{} = {}'.format(_key.decode(), r.get(_key).decode()))
                    return {
                        'title': key_name,
                        'keys': _keys,
                        'total': _total_keys,
                        'pool': key.redis_pool_name
                    }
                else:
                    return None
            else:
                return self.get_key_summary_single_multi_domain(r, key_name, key, max_keys_per_summary)

    def get_keys_summary(self, max_keys_per_summary=10, worker_id=None, hostname=None):
        for key_name in dir(self.keys):
            key = getattr(self.keys, key_name)
            if not isinstance(key, DomainsConfigKey):
                continue
            if getattr(key, 'keys_summary_type', None) == 'prefix-subkeys':
                yield self.get_key_summary_prefix_subkeys(key_name, key, worker_id, max_keys_per_summary, hostname=hostname)
            else:
                yield self.get_key_summary_single(key_name, key, worker_id, max_keys_per_summary, hostname=hostname)

    def set_worker_total_used_bytes(self, worker_id, total_used_bytes):
        value = str(total_used_bytes)
        self.keys.worker_total_used_bytes.set(worker_id, value)

    def get_worker_total_used_bytes(self, worker_id):
        value = self.keys.worker_total_used_bytes.get(worker_id)
        if value:
            try:
                value = int(value.decode())
            except:
                value = 0
        else:
            value = 0
        return value

    def alerts_push(self, alert):
        with self.keys.alerts.get_redis() as r:
            r.rpush(self.keys.alerts._(), json.dumps(alert))

    def alerts_pop(self):
        with self.keys.alerts.get_redis() as r:
            alert = r.lpop(self.keys.alerts._())
        return json.loads(alert) if alert else None

    def set_node_healthy(self, node_name, is_healthy):
        key = self.keys.node_healthy._(node_name)
        with self.keys.node_healthy.get_redis() as r:
            if is_healthy:
                r.set(key, "")
            else:
                r.delete(key)

    def iterate_healthy_node_names(self):
        for node_name in self.keys.node_healthy.iterate_prefix_key_suffixes():
            yield node_name

    def get_worker_last_clear_cache(self, worker_id):
        value = self.keys.worker_last_clear_cache.get(worker_id)
        return common.strptime(value.decode(), "%Y%m%dT%H%M%S") if value else None

    def set_worker_last_clear_cache(self, worker_id, last_clear_cache):
        self.keys.worker_last_clear_cache.set(worker_id, last_clear_cache.strftime("%Y%m%dT%H%M%S"))
