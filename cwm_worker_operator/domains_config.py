import json
import redis
import datetime
import requests
import traceback
from contextlib import contextmanager

from cwm_worker_operator import config
from cwm_worker_operator import logs


REDIS_KEY_PREFIX_WORKER_INITIALIZE = "worker:initialize"
REDIS_KEY_PREFIX_WORKER_AVAILABLE = "worker:available"
REDIS_KEY_WORKER_AVAILABLE = REDIS_KEY_PREFIX_WORKER_AVAILABLE + ":{}"
REDIS_KEY_WORKER_INGRESS_HOSTNAME = "worker:ingress:hostname:{}"
REDIS_KEY_WORKER_ERROR = "worker:error:{}"
REDIS_KEY_PREFIX_WORKER_ERROR = "worker:error"
REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER = "worker:error_attempt_number:{}"
REDIS_KEY_PREFIX_VOLUME_CONFIG = "worker:volume:config"
REDIS_KEY_VOLUME_CONFIG = REDIS_KEY_PREFIX_VOLUME_CONFIG + ":{}"
REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT = "worker:opstatus:ready_for_deployment"
REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE = "worker:opstatus:waiting_for_deployment"
REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE = "worker:force_update"
REDIS_KEY_PREFIX_WORKER_FORCE_DELETE = "worker:force_delete"
REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION = "deploymentid:last_action"
REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC = "deploymentid:minio-metrics"
REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS = "worker:aggregated-metrics"


class DomainsConfig(object):
    WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT = "TIMEOUT_WAITING_FOR_DEPLOYMENT"
    WORKER_ERROR_FAILED_TO_DEPLOY = "FAILED_TO_DEPLOY"
    WORKER_ERROR_INVALID_VOLUME_ZONE = "INVALID_VOLUME_ZONE"
    WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG = "FAILED_TO_GET_VOLUME_CONFIG"

    def __init__(self):
        print("REDIS_HOST={} REDIS_PORT={}".format(config.REDIS_HOST, config.REDIS_PORT))
        self.redis_pool = redis.BlockingConnectionPool(
            max_connections=config.REDIS_POOL_MAX_CONNECTIONS, timeout=config.REDIS_POOL_TIMEOUT,
            host=config.REDIS_HOST, port=config.REDIS_PORT
        )
        r = redis.Redis(connection_pool=self.redis_pool)
        try:
            assert r.ping()
        finally:
            r.close()

    @contextmanager
    def get_redis(self):
        r = redis.Redis(connection_pool=self.redis_pool)
        try:
            yield r
        finally:
            r.close()

    def get_worker_domains_ready_for_deployment(self):
        with self.get_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT))
            ]
        return worker_names

    def get_worker_domains_waiting_for_deployment_complete(self):
        with self.get_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE))
            ]
        return worker_names

    def get_worker_domains_waiting_for_initlization(self):
        with self.get_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE))
            ]
        return worker_names

    def get_cwm_api_volume_config(self, domain_name, metrics=None, force_update=False):
        start_time = datetime.datetime.now()
        if force_update:
            val = None
        else:
            with self.get_redis() as r:
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
            volume_config["__last_update"] = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            with self.get_redis() as r:
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
        with self.get_redis() as r:
            r.set(REDIS_KEY_WORKER_ERROR.format(domain_name), error_msg)
            self.del_worker_keys(r, domain_name, with_error=False, with_volume_config=False)

    def increment_worker_error_attempt_number(self, domain_name):
        with self.get_redis() as r:
            attempt_number = r.get(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name))
            attempt_number = int(attempt_number) if attempt_number else 0
            r.set(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name), str(attempt_number + 1))
        return attempt_number + 1

    def set_worker_ready_for_deployment(self, domain_name):
        with self.get_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name),
                  datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%f"))

    def get_worker_ready_for_deployment_start_time(self, domain_name):
        with self.get_redis() as r:
            try:
                dt = datetime.datetime.strptime(
                    r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name)).decode(),
                    "%Y%m%dT%H%M%S.%f")
            except Exception as e:
                logs.debug_info("exception: {}".format(e), domain_name=domain_name)
                if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                    traceback.print_exc()
                dt = datetime.datetime.now()
        return dt

    def get_volume_config_namespace_from_domain(self, metrics, domain_name):
        volume_config = self.get_cwm_api_volume_config(domain_name, metrics)
        if volume_config.get("hostname"):
            return volume_config, volume_config["hostname"].replace(".", "--")
        else:
            self.set_worker_error(domain_name, self.WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG)
            return volume_config, None

    def set_worker_waiting_for_deployment(self, domain_name):
        with self.get_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE, domain_name), "")

    def set_worker_available(self, domain_name, ingress_hostname):
        with self.get_redis() as r:
            self.del_worker_keys(r, domain_name, with_volume_config=False, with_available=False, with_ingress=False)
            r.set(REDIS_KEY_WORKER_AVAILABLE.format(domain_name), "")
            r.set(REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name), ingress_hostname)

    def del_worker_keys(self, redis_connection, domain_name, with_error=True, with_volume_config=True, with_available=True, with_ingress=True):
        r = redis_connection if redis_connection else redis.Redis(connection_pool=self.redis_pool)
        try:
            r.delete(
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name),
                *([
                  REDIS_KEY_WORKER_AVAILABLE.format(domain_name)
                ] if with_available else []),
                *([
                  REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name)
                  ] if with_ingress else []),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE, domain_name),
                *([
                    REDIS_KEY_WORKER_ERROR.format(domain_name),
                    REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name)
                ] if with_error else []),
                *([
                    REDIS_KEY_VOLUME_CONFIG.format(domain_name)
                ] if with_volume_config else []),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE, domain_name),
                "{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE, domain_name),
            )
        finally:
            if not redis_connection:
                r.close()

    def set_worker_force_update(self, domain_name):
        with self.get_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE, domain_name), "")

    def set_worker_force_delete(self, domain_name):
        with self.get_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE, domain_name), "")

    def iterate_domains_to_delete(self):
        with self.get_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_FORCE_DELETE))
            ]
        return worker_names

    def get_domains_force_update(self):
        with self.get_redis() as r:
            worker_names = [
                key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE), "")
                for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_FORCE_UPDATE))
            ]
        return worker_names

    def get_worker_aggregated_metrics(self, domain_name, clear=False):
        with self.get_redis() as r:
            if clear:
                value = r.getset("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name), '')
            else:
                value = r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name))
            if value:
                return json.loads(value.decode())
            else:
                return None

    def get_deployment_api_metrics(self, namespace_name):
        with self.get_redis() as r:
            base_key = "{}:{}:".format(REDIS_KEY_PREFIX_DEPLOYMENT_API_METRIC, namespace_name)
            return {
                key.decode().replace(base_key, ""): r.get(key).decode()
                for key in r.keys(base_key + "*")
            }

    def set_worker_aggregated_metrics(self, domain_name, agg_metrics):
        with self.get_redis() as r:
            r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_AGGREGATED_METRICS, domain_name), json.dumps(agg_metrics))

    def get_deployment_last_action(self, namespace_name):
        with self.get_redis() as r:
            value = r.get("{}:{}".format(REDIS_KEY_PREFIX_DEPLOYMENT_LAST_ACTION, namespace_name))
            return datetime.datetime.strptime(value.decode(), "%Y%m%dT%H%M%S.%f") if value else None
