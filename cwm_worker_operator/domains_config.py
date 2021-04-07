import json
import redis
import requests
import traceback
from contextlib import contextmanager

from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator import common


# ingress_redis - keys shared with cwm-worker-ingress
REDIS_KEY_PREFIX_WORKER_INITIALIZE = "worker:initialize"
REDIS_KEY_PREFIX_WORKER_AVAILABLE = "worker:available"
REDIS_KEY_WORKER_AVAILABLE = REDIS_KEY_PREFIX_WORKER_AVAILABLE + ":{}"
REDIS_KEY_WORKER_INGRESS_HOSTNAME = "worker:ingress:hostname:{}"
REDIS_KEY_WORKER_ERROR = "worker:error:{}"
REDIS_KEY_PREFIX_WORKER_ERROR = "worker:error"

# internal_redis - keys used internally only by cwm-worker-operator
REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER = "worker:error_attempt_number:{}"
REDIS_KEY_PREFIX_VOLUME_CONFIG = "worker:volume:config"
REDIS_KEY_VOLUME_CONFIG = REDIS_KEY_PREFIX_VOLUME_CONFIG + ":{}"
REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT = "worker:opstatus:ready_for_deployment"
REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE = "worker:opstatus:waiting_for_deployment"
REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE = "worker:force_update"
REDIS_KEY_PREFIX_WORKER_FORCE_DELETE = "worker:force_delete"
REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS = "worker:aggregated-metrics"
REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS_LAST_SENT_UPDATE = "worker:aggregated-metrics-last-sent-update"
REDIS_KEY_PREFIX_WORKER_TOTAL_USED_BYTES = "worker:total-used-bytes"
REDIS_KEY_ALERTS = "alerts"

# metrics_redis - keys shared with deployments to get metrics
REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION = "deploymentid:last_action"
REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC = "deploymentid:minio-metrics"


ALL_REDIS_KEYS = {
    # ingress redis pool
    REDIS_KEY_PREFIX_WORKER_INITIALIZE: {'type': 'prefix', 'pool': 'ingress'},
    REDIS_KEY_PREFIX_WORKER_AVAILABLE: {'type': 'prefix', 'pool': 'ingress'},
    REDIS_KEY_WORKER_AVAILABLE: {'type': 'template', 'duplicate_of': REDIS_KEY_PREFIX_WORKER_AVAILABLE, 'pool': 'ingress'},
    REDIS_KEY_WORKER_INGRESS_HOSTNAME: {'type': 'template', 'pool': 'ingress'},
    REDIS_KEY_WORKER_ERROR: {'type': 'template', 'pool': 'ingress'},
    REDIS_KEY_PREFIX_WORKER_ERROR: {'type': 'prefix', 'duplicate_of': REDIS_KEY_WORKER_ERROR, 'pool': 'ingress'},

    # internal redis pool
    REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER: {'type': 'template', 'pool': 'internal'},
    REDIS_KEY_PREFIX_VOLUME_CONFIG: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_VOLUME_CONFIG: {'type': 'template', 'duplicate_of': REDIS_KEY_PREFIX_VOLUME_CONFIG, 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_FORCE_DELETE: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS_LAST_SENT_UPDATE: {'type': 'prefix', 'pool': 'internal'},
    REDIS_KEY_PREFIX_WORKER_TOTAL_USED_BYTES: {'type': 'prefix', 'pool': 'internal'},

    # metrics redis pool
    REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION: {'type': 'prefix-subkeys', 'use_namespace': True, 'pool': 'metrics'},
    REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC: {'type': 'prefix-subkeys', 'use_namespace': True, 'pool': 'metrics'},
}


class DomainsConfig(object):
    WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT = "TIMEOUT_WAITING_FOR_DEPLOYMENT"
    WORKER_ERROR_FAILED_TO_DEPLOY = "FAILED_TO_DEPLOY"
    WORKER_ERROR_INVALID_VOLUME_ZONE = "INVALID_VOLUME_ZONE"
    WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG = "FAILED_TO_GET_VOLUME_CONFIG"

    def __init__(self):
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

    def get_worker_domains_ready_for_deployment(self):
        with self.get_internal_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT))
            ]
        return worker_names

    def get_worker_domains_waiting_for_deployment_complete(self):
        with self.get_internal_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE))
            ]
        return worker_names

    def get_worker_domains_waiting_for_initlization(self):
        with self.get_ingress_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE))
            ]
        return worker_names

    def get_cwm_api_volume_config(self, domain_name, metrics=None, force_update=False):
        start_time = common.now()
        if force_update:
            val = None
        else:
            with self.get_internal_redis() as r:
                val = r.get(REDIS_KEY_VOLUME_CONFIG.format(domain_name))
        if val is None:
            try:
                volume_config = requests.get("{}/volume/{}".format(config.CWM_API_URL, domain_name)).json()
                is_success = True
            except Exception as e:
                if config.DEBUG and config.DEBUG_VERBOSITY > 5:
                    traceback.print_exc()
                volume_config = {"__error": str(e)}
                is_success = False
            volume_config["__last_update"] = common.now().strftime("%Y%m%dT%H%M%S")
            # TODO: add support for multiple hostnames per domain / multiple domains per customer
            if volume_config.get("hostname"):
                volume_config["hostname"] = domain_name
            with self.get_internal_redis() as r:
                r.set(REDIS_KEY_VOLUME_CONFIG.format(domain_name), json.dumps(volume_config))
            if metrics:
                if is_success:
                    metrics.cwm_api_volume_config_success_from_api(domain_name, start_time)
                else:
                    metrics.cwm_api_volume_config_error_from_api(domain_name, start_time)
            return volume_config
        else:
            if metrics:
                metrics.cwm_api_volume_config_success_from_cache(domain_name, start_time)
            return json.loads(val)

    def set_worker_error(self, domain_name, error_msg):
        with self.get_ingress_redis() as r:
            r.set(REDIS_KEY_WORKER_ERROR.format(domain_name), error_msg)
        self.del_worker_keys(domain_name, with_error=False, with_volume_config=False)

    def increment_worker_error_attempt_number(self, domain_name):
        with self.get_internal_redis() as r:
            attempt_number = r.get(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name))
            attempt_number = int(attempt_number) if attempt_number else 0
            r.set(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name), str(attempt_number + 1))
        return attempt_number + 1

    def set_worker_ready_for_deployment(self, domain_name):
        with self.get_internal_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name),
                  common.now().strftime("%Y%m%dT%H%M%S.%f"))

    def get_worker_ready_for_deployment_start_time(self, domain_name):
        with self.get_internal_redis() as r:
            try:
                dt = common.strptime(
                    r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name)).decode(),
                    "%Y%m%dT%H%M%S.%f")
            except Exception as e:
                logs.debug_info("exception: {}".format(e), domain_name=domain_name)
                if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                    traceback.print_exc()
                dt = common.now()
        return dt

    def get_volume_config_namespace_from_domain(self, metrics, domain_name):
        volume_config = self.get_cwm_api_volume_config(domain_name, metrics)
        if volume_config.get("hostname"):
            return volume_config, volume_config["hostname"].replace(".", "--")
        else:
            self.set_worker_error(domain_name, self.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
            return volume_config, None

    def set_worker_waiting_for_deployment(self, domain_name):
        with self.get_internal_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE, domain_name), "")

    def is_worker_waiting_for_deployment(self, domain_name):
        with self.get_ingress_redis() as r:
            for key in [
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name),
            ]:
                if r.exists(key):
                    return True
        with self.get_internal_redis() as r:
            for key in [
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE, domain_name)
            ]:
                if r.exists(key):
                    return True
        return False

    def set_worker_available(self, domain_name, ingress_hostname):
        self.del_worker_keys(domain_name, with_volume_config=False, with_available=False, with_ingress=False)
        with self.get_ingress_redis() as r:
            r.set(REDIS_KEY_WORKER_AVAILABLE.format(domain_name), "")
            r.set(REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name), json.dumps(ingress_hostname))

    def is_worker_available(self, domain_name):
        with self.get_ingress_redis() as r:
            return r.exists(REDIS_KEY_WORKER_AVAILABLE.format(domain_name))

    def del_worker_keys(self, domain_name, with_error=True, with_volume_config=True, with_available=True, with_ingress=True, with_metrics=False):
        namespace_name = domain_name.replace('.', '--')
        with self.get_ingress_redis() as r:
            r.delete(
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name),
                *([
                      REDIS_KEY_WORKER_AVAILABLE.format(domain_name)
                  ] if with_available else []),
                *([
                      REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name)
                  ] if with_ingress else []),
                *([
                      REDIS_KEY_WORKER_ERROR.format(domain_name),
                  ] if with_error else []),
            )
        with self.get_internal_redis() as r:
            r.delete(
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE, domain_name),
                *([
                      REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name)
                  ] if with_error else []),
                *([
                      REDIS_KEY_VOLUME_CONFIG.format(domain_name)
                  ] if with_volume_config else []),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE, domain_name),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE, domain_name),
                *([
                      '{}:{}'.format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name),
                      '{}:{}'.format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS_LAST_SENT_UPDATE, domain_name),
                      '{}:{}'.format(REDIS_KEY_PREFIX_WORKER_TOTAL_USED_BYTES, domain_name),
                  ] if with_metrics else [])
            )
        if with_metrics:
            with self.get_metrics_redis() as r:
                keys = [key.decode() for key in
                        r.keys('{}:{}:*'.format(REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC, namespace_name))]
                if keys:
                    r.delete(*keys)
                keys = [key.decode() for key in
                        r.keys('{}:{}:*'.format(REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION, namespace_name))]
                if keys:
                    r.delete(*keys)

    def set_worker_force_update(self, domain_name):
        with self.get_internal_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE, domain_name), "")

    def set_worker_force_delete(self, domain_name, allow_cancel=False):
        with self.get_internal_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE, domain_name), "allow_cancel" if allow_cancel else "")

    def del_worker_force_delete(self, domain_name):
        with self.get_internal_redis() as r:
            r.delete("{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE, domain_name))

    def get_worker_force_delete(self, domain_name):
        with self.get_internal_redis() as r:
            value = r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE, domain_name))
            if value is not None:
                return {'domain_name': domain_name, 'allow_cancel': value == b"allow_cancel"}
            else:
                return None

    def iterate_domains_to_delete(self):
        with self.get_internal_redis() as r:
            workers_to_delete = [
                {
                    "domain_name": key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE), ""),
                    "allow_cancel": r.get(key) == b"allow_cancel"
                }
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE))
            ]
        return workers_to_delete

    def get_domains_force_update(self):
        with self.get_internal_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE))
            ]
        return worker_names

    def get_worker_aggregated_metrics(self, domain_name, clear=False):
        with self.get_internal_redis() as r:
            if clear:
                value = r.getset("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name), '')
            else:
                value = r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name))
            if value:
                return json.loads(value.decode())
            else:
                return None

    def get_deployment_api_metrics(self, namespace_name, bucket):
        with self.get_metrics_redis() as r:
            base_key = "{}:{}:{}:".format(REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC, namespace_name, bucket)
            return {
                key.decode().replace(base_key, ""): r.get(key).decode()
                for key in r.keys(base_key + "*")
            }

    def set_worker_aggregated_metrics(self, domain_name, agg_metrics):
        with self.get_internal_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name), json.dumps(agg_metrics))

    # returns tuple of datetimes (last_sent_update, last_update)
    # last_sent_update = the time when the last update was sent to cwm api
    # last_update = the time of the last update which was sent
    def get_worker_aggregated_metrics_last_sent_update(self, domain_name):
        with self.get_internal_redis() as r:
            value = r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS_LAST_SENT_UPDATE, domain_name))
            if value:
                last_sent_update, last_update = value.decode().split(',')
                last_sent_update = common.strptime(last_sent_update, '%Y%m%d%H%M%S')
                last_update = common.strptime(last_update, '%Y%m%d%H%M%S')
                return last_sent_update, last_update
            else:
                return None, None

    def set_worker_aggregated_metrics_last_sent_update(self, domain_name, last_update):
        with self.get_internal_redis() as r:
            value = '{},{}'.format(common.now().strftime('%Y%m%d%H%M%S'), last_update.strftime('%Y%m%d%H%M%S'))
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS_LAST_SENT_UPDATE, domain_name), value)

    def get_deployment_last_action(self, namespace_name, buckets=('http', 'https')):
        latest_value = None
        with self.get_metrics_redis() as r:
            for bucket in buckets:
                value = r.get("{}:{}:{}".format(REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION, namespace_name, bucket))
                if value:
                    value = value.decode().split('.')[0].replace('-', '').replace(':', '')
                    value = common.strptime(value, "%Y%m%dT%H%M%S")
                    if latest_value is None or value > latest_value:
                        latest_value = value
        return latest_value if latest_value else None

    def get_key_summary_single_multi_domain(self, r, key, max_keys_per_summary, pool):
        match = '{}:*'.format(key)
        _keys = []
        _total_keys = 0
        for _key in r.scan_iter(match):
            _total_keys += 1
            if len(_keys) < max_keys_per_summary:
                _keys.append(_key.decode())
        return {
            'title': key,
            'keys': _keys,
            'total': _total_keys,
            'pool': pool
        }

    def get_key_summary_single(self, key, key_config, domain_name, max_keys_per_summary):
        with getattr(self, 'get_{}_redis'.format(key_config['pool']))() as r:
            if key_config['type'] == 'template':
                key = key.replace(':{}', '')
            if domain_name:
                _key = '{}:{}'.format(key, domain_name.replace('.', '--')) if key_config.get('use_namespace') else '{}:{}'.format(key, domain_name)
                value = r.get(_key)
                if value:
                    value = value.decode()
                return {
                    'title': key,
                    'keys': ['{} = {}'.format(_key, value)],
                    'total': 1 if value else 0,
                    'pool': key_config['pool']
                }
            else:
                return self.get_key_summary_single_multi_domain(r, key, max_keys_per_summary, key_config['pool'])

    def get_key_summary_prefix_subkeys(self, key, key_config, domain_name, max_keys_per_summary):
        with getattr(self, 'get_{}_redis'.format(key_config['pool']))() as r:
            if domain_name:
                _key = '{}:{}'.format(key, domain_name.replace('.', '--')) if key_config.get('use_namespace') else '{}:{}'.format(key, domain_name)
                match = '{}:*'.format(_key)
                _keys = []
                _total_keys = 0
                for _key in r.scan_iter(match):
                    _total_keys += 1
                    if len(_keys) < max_keys_per_summary*3:
                        _keys.append('{} = {}'.format(_key.decode(), r.get(_key).decode()))
                return {
                    'title': key,
                    'keys': _keys,
                    'total': _total_keys,
                    'pool': key_config['pool']
                }
            else:
                return self.get_key_summary_single_multi_domain(r, key, max_keys_per_summary, key_config['pool'])

    def get_keys_summary(self, max_keys_per_summary=10, domain_name=None):
        for key, key_config in ALL_REDIS_KEYS.items():
            if key_config.get('duplicate_of'):
                continue
            if key_config['type'] == 'prefix-subkeys':
                yield self.get_key_summary_prefix_subkeys(key, key_config, domain_name, max_keys_per_summary)
            elif key_config['type'] in ['prefix', 'template']:
                yield self.get_key_summary_single(key, key_config, domain_name, max_keys_per_summary)
            else:
                raise NotImplementedError('key_config type not supported yet: {}'.format(key_config['type']))

    def set_worker_total_used_bytes(self, domain_name, total_used_bytes):
        with self.get_internal_redis() as r:
            value = str(total_used_bytes)
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_TOTAL_USED_BYTES, domain_name), value)

    def get_worker_total_used_bytes(self, domain_name):
        with self.get_internal_redis() as r:
            value = r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_TOTAL_USED_BYTES, domain_name))
            if value:
                try:
                    value = int(value.decode())
                except:
                    value = 0
            else:
                value = 0
            return value

    def alerts_push(self, alert):
        with self.get_internal_redis() as r:
            r.rpush(REDIS_KEY_ALERTS, json.dumps(alert))

    def alerts_pop(self):
        with self.get_internal_redis() as r:
            alert = r.lpop(REDIS_KEY_ALERTS)
        return json.loads(alert) if alert else None
