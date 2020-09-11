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

METRICS_SAVE_PATH_PREFIX = os.environ.get("METRICS_SAVE_PATH_PREFIX", ".metrics")
METRICS_GROUP_DEPLOYER_PATH_SUFFIX = os.environ.get("METRICS_GROUP_DEPLOYER_PATH_SUFFIX", "deployer")
METRICS_GROUP_ERRORHANDLER_PATH_SUFFIX = os.environ.get("METRICS_GROUP_ERRORHANDLER_PATH_SUFFIX", "errorhandler")
METRICS_SAVE_INTERVAL_SECONDS = int(os.environ.get("METRICS_SAVE_INTERVAL_SECONDS", "5"))

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

CWM_API_URL = os.environ["CWM_API_URL"]
CWM_ZONE = os.environ["CWM_ZONE"]

PACKAGES_READER_GITHUB_USER = os.environ["PACKAGES_READER_GITHUB_USER"]
PACKAGES_READER_GITHUB_TOKEN = os.environ["PACKAGES_READER_GITHUB_TOKEN"]
PULL_SECRET = '{"auths":{"docker.pkg.github.com":{"auth":"__AUTH__"}}}'.replace("__AUTH__", base64.b64encode("{}:{}".format(PACKAGES_READER_GITHUB_USER, PACKAGES_READER_GITHUB_TOKEN).encode()).decode())

DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS = float(os.environ.get("DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS") or "10.0")
DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "0.1")

ERRORHANDLER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("ERRORHANDLER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "0.1")
ERRORHANDLER_WAIT_DEPLOYMENT_READY_MAX_SECONDS = float(os.environ.get("ERRORHANDLER_WAIT_DEPLOYMENT_READY_MAX_SECONDS") or "15.0")

WORKER_ERROR_TIMEOUT_WAITING_FOR_DEPLOYMENT = "TIMEOUT_WAITING_FOR_DEPLOYMENT"
WORKER_ERROR_FAILED_TO_DEPLOY = "FAILED_TO_DEPLOY"
WORKER_ERROR_DIFFERENT_VOLUME_CONFIGS = "DIFFERENT_VOLUME_CONFIGS"
WORKER_ERROR_INVALID_VOLUME_ZONE = "INVALID_VOLUME_ZONE"
WORKER_ERROR_FAILED_TO_GET_VOLUME_CONFIG = "FAILED_TO_GET_VOLUME_CONFIG"

WORKER_ERROR_MAX_ATTEMPTS = int(os.environ.get("WORKER_ERROR_MAX_ATTEMPTS", "5"))

CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG = json.loads(os.environ.get("CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG_JSON") or '{}')
MINIO_EXTRA_CONFIG = json.loads(os.environ.get("MINIO_EXTRA_CONFIG_JSON") or '{}')

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


def get_error_worker_domains(redis_pool):
    r = redis.Redis(connection_pool=redis_pool)
    worker_names = [
        key.decode().replace("{}:".format(REDIS_KEY_PREFIX_WORKER_ERROR), "")
        for key in r.keys("{}:*".format(REDIS_KEY_PREFIX_WORKER_ERROR))
    ]
    r.close()
    return worker_names


def get_cwm_api_volume_config(redis_pool, domain_name, metrics):
    r = redis.Redis(connection_pool=redis_pool)
    val = r.get(REDIS_KEY_VOLUME_CONFIG.format(domain_name))
    r.close()
    if val is None:
        try:
            volume_config =  requests.get("{}/volume/{}".format(CWM_API_URL, domain_name)).json()
            metrics.send("loaded volume config from cwm_api")
        except Exception as e:
            traceback.print_exc()
            volume_config = {"__error": str(e)}
            metrics.send("failed getting volume config from cwm_api")
        volume_config["__last_update"] = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        r = redis.Redis(connection_pool=redis_pool)
        r.set(REDIS_KEY_VOLUME_CONFIG.format(domain_name), json.dumps(volume_config))
        r.close()
        return volume_config
    else:
        metrics.send("loaded volume config from cache")
        return json.loads(val)


def set_worker_available(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    r.set(REDIS_KEY_WORKER_AVAILABLE.format(domain_name), "")
    r.close()


def del_worker_initialize(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    r.delete("{}:{}".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name))
    r.close()


def set_worker_error(redis_pool, domain_name, error_msg, metrics, error_attempt_number=None):
    metrics.send("error: {}".format(error_msg))
    r = redis.Redis(connection_pool=redis_pool)
    r.set(REDIS_KEY_WORKER_ERROR.format(domain_name), error_msg)
    del_worker_keys(r, domain_name, with_error=False, with_volume_config=False)
    if error_attempt_number:
        r.set(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name), str(error_attempt_number+1))
    r.close()


def del_worker_error(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    r.delete(REDIS_KEY_WORKER_ERROR.format(domain_name))
    r.close()


def set_worker_ingress_hostname(redis_pool, domain_name, ingress_hostname):
    r = redis.Redis(connection_pool=redis_pool)
    r.set(REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name), ingress_hostname)
    r.close()


def get_worker_error_attempt_number(redis_pool, domain_name):
    r = redis.Redis(connection_pool=redis_pool)
    attempt_number = r.get(REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name))
    attempt_number = int(attempt_number) if attempt_number else 1
    r.close()
    return attempt_number


def del_worker_keys(redis_connection, domain_name, with_error=True, with_volume_config=True):
    redis_connection.delete(
        "{}:{}".format(REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name),
        REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name),
        REDIS_KEY_WORKER_AVAILABLE.format(domain_name),
        *([
            REDIS_KEY_WORKER_ERROR.format(domain_name),
            REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name)
        ] if with_error else []),
        *([
            REDIS_KEY_VOLUME_CONFIG.format(domain_name)
        ] if with_volume_config else [])
    )
