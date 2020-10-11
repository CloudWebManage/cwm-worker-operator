import os
import redis
import requests
import base64
import json
import datetime
import traceback

DEBUG = os.environ.get("DEBUG") == "yes"

# higher numbers = more debug logs
DEBUG_VERBOSITY = int(os.environ.get("DEBUG_VERBOSITY") or "10")

REDIS_HOST = os.environ.get("REDIS_HOST") or "localhost"
REDIS_PORT = int(os.environ.get("REDIS_PORT") or "6379")
REDIS_POOL_MAX_CONNECTIONS = int(os.environ.get("REDIS_POOL_MAX_CONNECTIONS") or "50")
REDIS_POOL_TIMEOUT = int(os.environ.get("REDIS_POOL_TIMEOUT") or "5")

REDIS_KEY_PREFIX_WORKER_INITIALIZE = "worker:initialize"
REDIS_KEY_WORKER_AVAILABLE = "worker:available:{}"
REDIS_KEY_WORKER_INGRESS_HOSTNAME = "worker:ingress:hostname:{}"
REDIS_KEY_WORKER_ERROR = "worker:error:{}"
REDIS_KEY_PREFIX_WORKER_ERROR = "worker:error"
REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER = "worker:error_attempt_number:{}"
REDIS_KEY_VOLUME_CONFIG = "worker:volume:config:{}"
REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT = "worker:opstatus:ready_for_deployment"
REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE = "worker:opstatus:waiting_for_deployment"

CWM_API_URL = os.environ["CWM_API_URL"]
CWM_ZONE = os.environ["CWM_ZONE"]

PACKAGES_READER_GITHUB_USER = os.environ.get("PACKAGES_READER_GITHUB_USER")
PACKAGES_READER_GITHUB_TOKEN = os.environ.get("PACKAGES_READER_GITHUB_TOKEN")
if PACKAGES_READER_GITHUB_TOKEN and PACKAGES_READER_GITHUB_USER:
    PULL_SECRET = '{"auths":{"docker.pkg.github.com":{"auth":"__AUTH__"}}}'.replace("__AUTH__", base64.b64encode("{}:{}".format(PACKAGES_READER_GITHUB_USER, PACKAGES_READER_GITHUB_TOKEN).encode()).decode())
else:
    PULL_SECRET = ''

INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "0.001")

DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS = float(os.environ.get("DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS") or "10.0")
DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "0.01")

WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT = "TIMEOUT_WAITING_FOR_DEPLOYMENT"
WORKER_ERROR_FAILED_TO_DEPLOY = "FAILED_TO_DEPLOY"
WORKER_ERROR_INVALID_VOLUME_ZONE = "INVALID_VOLUME_ZONE"
WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG = "FAILED_TO_GET_VOLUME_CONFIG"

WORKER_ERROR_MAX_ATTEMPTS = int(os.environ.get("WORKER_ERROR_MAX_ATTEMPTS", "5"))

WAITER_VERIFY_WORKER_ACCESS = (os.environ.get("WAITER_VERIFY_WORKER_ACCESS") or "yes") == "yes"

CACHE_MINIO_VERSIONS = [v.strip() for v in (os.environ.get("CACHE_MINIO_VERSIONS") or "").split(",")]
CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG = json.loads(os.environ.get("CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG_JSON") or '{}')
MINIO_EXTRA_CONFIG = json.loads(os.environ.get("MINIO_EXTRA_CONFIG_JSON") or '{}')
CWM_WORKER_EXTRA_OBJECTS = json.loads(os.environ.get("CWM_WORKER_EXTRA_OBJECTS_JSON") or '[]')

PROMETHEUS_METRICS_PORT_INITIALIZER = int(os.environ.get("PROMETHEUS_METRICS_PORT_INITIALIZER") or "8081")
PROMETHEUS_METRICS_PORT_DEPLOYER = int(os.environ.get("PROMETHEUS_METRICS_PORT_DEPLOYER") or "8082")
PROMETHEUS_METRICS_PORT_WAITER = int(os.environ.get("PROMETHEUS_METRICS_PORT_WAITER") or "8083")
PROMETHEUS_METRICS_WITH_DOMAIN_LABEL = os.environ.get("PROMETHEUS_METRICS_WITH_DOMAIN_LABEL") == "yes"

DELETER_DEFAULT_DELETE_NAMESPACE = os.environ.get("DELETER_DEFAULT_DELETE_NAMESPACE") == "yes"
DELETER_DEFAULT_DELETE_HELM = (os.environ.get("DELETER_DEFAULT_DELETE_HELM") or "yes") == "yes"

DEPLOYER_USE_EXTERNAL_SERVICE = os.environ.get("DEPLOYER_USE_EXTERNAL_SERVICE") == "yes"
DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS = os.environ.get("DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS") == "yes"

def get_redis_pool():
    print("REDIS_HOST={} REDIS_PORT={}".format(REDIS_HOST, REDIS_PORT))
    pool = redis.BlockingConnectionPool(
        max_connections=REDIS_POOL_MAX_CONNECTIONS, timeout=REDIS_POOL_TIMEOUT,
        host=REDIS_HOST, port=REDIS_PORT
    )
    r = redis.Redis(connection_pool=pool)
    assert r.ping()
    r.close()
    return pool


def get_worker_domains_waiting_for_initlization(redis_pool):
    r = redis.Redis(connection_pool=redis_pool)
    worker_names = [
        key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE), "")
        for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE))
    ]
    r.close()
    return worker_names


def get_cwm_api_volume_config(redis_pool, domain_name, metrics=None):
    start_time = datetime.datetime.now()
    r = redis.Redis(connection_pool=redis_pool)
    val = r.get(REDIS_KEY_VOLUME_CONFIG.format(domain_name))
    r.close()
    if val is None:
        try:
            volume_config =  requests.get("{}/volume/{}".format(CWM_API_URL, domain_name)).json()
            is_success = True
        except Exception as e:
            if DEBUG and DEBUG_VERBOSITY > 5:
                traceback.print_exc()
            volume_config = {"__error": str(e)}
            is_success = False
        volume_config["__last_update"] = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        r = redis.Redis(connection_pool=redis_pool)
        r.set(REDIS_KEY_VOLUME_CONFIG.format(domain_name), json.dumps(volume_config))
        r.close()
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


def set_worker_available(redis_pool, domain_name, ingress_hostname):
    r = redis.Redis(connection_pool=redis_pool)
    del_worker_keys(r, domain_name, with_volume_config=False, with_available=False, with_ingress=False)
    r.set(REDIS_KEY_WORKER_AVAILABLE.format(domain_name), "")
    r.set(REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name), ingress_hostname)
    r.close()


def set_worker_error(redis_pool, domain_name, error_msg):
    r = redis.Redis(connection_pool=redis_pool)
    r.set(REDIS_KEY_WORKER_ERROR.format(domain_name), error_msg)
    del_worker_keys(r, domain_name, with_error=False, with_volume_config=False)
    r.close()


def increment_worker_error_attempt_number(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    attempt_number = r.get(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name))
    attempt_number = int(attempt_number) if attempt_number else 0
    r.set(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name), str(attempt_number + 1))
    r.close()
    return attempt_number + 1


def del_worker_keys(redis_connection, domain_name, with_error=True, with_volume_config=True, with_available=True, with_ingress=True):
    redis_connection.delete(
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
        ] if with_volume_config else [])
    )


def set_worker_ready_for_deployment(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name), datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%f"))
    r.close()


def get_worker_ready_for_deployment_start_time(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    dt = datetime.datetime.strptime(r.get("{}:{}".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name)).decode(), "%Y%m%dT%H%M%S.%f")
    r.close()
    return dt


def get_worker_domains_ready_for_deployment(redis_pool):
    r = redis.Redis(connection_pool=redis_pool)
    worker_names = [
        key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT), "")
        for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT))
    ]
    r.close()
    return worker_names


def set_worker_waiting_for_deployment(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    r.set("{}:{}".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE, domain_name), "")
    r.close()


def get_worker_domains_waiting_for_deployment_complete(redis_pool):
    r = redis.Redis(connection_pool=redis_pool)
    worker_names = [
        key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE), "")
        for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_WAITING_FOR_DEPLOYMENT_COMPLETE))
    ]
    r.close()
    return worker_names
