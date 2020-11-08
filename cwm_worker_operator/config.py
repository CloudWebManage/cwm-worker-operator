import os
import base64
import json

DEBUG = os.environ.get("DEBUG") == "yes"

# higher numbers = more debug logs
DEBUG_VERBOSITY = int(os.environ.get("DEBUG_VERBOSITY") or "10")

REDIS_HOST = os.environ.get("REDIS_HOST") or "localhost"
REDIS_PORT = int(os.environ.get("REDIS_PORT") or "6379")
REDIS_POOL_MAX_CONNECTIONS = int(os.environ.get("REDIS_POOL_MAX_CONNECTIONS") or "50")
REDIS_POOL_TIMEOUT = int(os.environ.get("REDIS_POOL_TIMEOUT") or "5")

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

WORKER_ERROR_MAX_ATTEMPTS = int(os.environ.get("WORKER_ERROR_MAX_ATTEMPTS", "5"))

WAITER_VERIFY_WORKER_ACCESS = (os.environ.get("WAITER_VERIFY_WORKER_ACCESS") or "yes") == "yes"

CACHE_MINIO_VERSIONS = [v.strip() for v in (os.environ.get("CACHE_MINIO_VERSIONS") or "").split(",") if v and v.strip()]
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

DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "1")
UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "30")
# '5m', '10m', '30m', '1h', '3h', '6h', '12h', '24h', '48h', '72h', '96h'
FORCE_DELETE_NETWORK_RECEIVE_PERIOD = os.environ.get("FORCE_DELETE_NETWORK_RECEIVE_PERIOD") or "5m"
FORCE_DELETE_MAX_PERIOD_VALUE = float(os.environ.get("FORCE_DELETE_MAX_PERIOD_VALUE") or "0.0")
FORCE_UPDATE_MAX_HOURS_TTL = float(os.environ.get("FORCE_UPDATE_MAX_HOURS_TTL") or "24")
FORCE_DELETE_GRACE_PERIOD_HOURS = float(os.environ.get("FORCE_DELETE_GRACE_PERIOD_HOURS") or "1")

LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS = int(os.environ.get("LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS") or "300")
