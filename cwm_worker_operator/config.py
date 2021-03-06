import os
import base64
import json

DEBUG = os.environ.get("DEBUG") == "yes" or os.environ.get("ENABLE_DEBUG") == "yes"

# higher numbers = more debug logs
DEBUG_VERBOSITY = int(os.environ.get("DEBUG_VERBOSITY") or "10")

_default_redis_host = os.environ.get("REDIS_HOST") or "localhost"
_default_redis_port = int(os.environ.get("REDIS_PORT") or "6379")
_default_redis_pool_max_connections = int(os.environ.get("REDIS_POOL_MAX_CONNECTIONS") or "50")
_default_redis_pool_timeout = int(os.environ.get("REDIS_POOL_TIMEOUT") or "5")

INGRESS_REDIS_HOST = os.environ.get("INGRESS_REDIS_HOST") or _default_redis_host
INGRESS_REDIS_PORT = int(os.environ.get("INGRESS_REDIS_PORT") or _default_redis_port)
INGRESS_REDIS_POOL_MAX_CONNECTIONS = int(os.environ.get("INGRESS_REDIS_POOL_MAX_CONNECTIONS") or _default_redis_pool_max_connections)
INGRESS_REDIS_POOL_TIMEOUT = int(os.environ.get("INGRESS_REDIS_POOL_TIMEOUT") or _default_redis_pool_timeout)
INGRESS_REDIS_DB = int(os.environ.get("INGRESS_REDIS_DB") or "0")

INTERNAL_REDIS_HOST = os.environ.get("INTERNAL_REDIS_HOST") or _default_redis_host
INTERNAL_REDIS_PORT = int(os.environ.get("INTERNAL_REDIS_PORT") or _default_redis_port)
INTERNAL_REDIS_POOL_MAX_CONNECTIONS = int(os.environ.get("INTERNAL_REDIS_POOL_MAX_CONNECTIONS") or _default_redis_pool_max_connections)
INTERNAL_REDIS_POOL_TIMEOUT = int(os.environ.get("INTERNAL_REDIS_POOL_TIMEOUT") or _default_redis_pool_timeout)
INTERNAL_REDIS_DB = int(os.environ.get("INGRESS_REDIS_DB") or "1")

METRICS_REDIS_HOST = os.environ.get("METRICS_REDIS_HOST") or _default_redis_host
METRICS_REDIS_PORT = int(os.environ.get("METRICS_REDIS_PORT") or _default_redis_port)
METRICS_REDIS_POOL_MAX_CONNECTIONS = int(os.environ.get("METRICS_REDIS_POOL_MAX_CONNECTIONS") or _default_redis_pool_max_connections)
METRICS_REDIS_POOL_TIMEOUT = int(os.environ.get("METRICS_REDIS_POOL_TIMEOUT") or _default_redis_pool_timeout)
METRICS_REDIS_DB = int(os.environ.get("INGRESS_REDIS_DB") or "2")

CWM_API_URL = os.environ["CWM_API_URL"]
CWM_API_KEY = os.environ["CWM_API_KEY"]
CWM_API_SECRET = os.environ["CWM_API_SECRET"]
CWM_ZONE = os.environ["CWM_ZONE"]
CWM_ADDITIONAL_ZONES = [z.strip() for z in (os.environ.get("CWM_ADDITIONAL_ZONES") or '').split(',') if z.strip()]

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
PROMETHEUS_METRICS_PORT_DELETER = int(os.environ.get("PROMETHEUS_METRICS_PORT_DELETER") or "8084")
PROMETHEUS_METRICS_PORT_UPDATER = int(os.environ.get("PROMETHEUS_METRICS_PORT_UPDATER") or "8085")
PROMETHEUS_METRICS_PORT_METRICS_UPDATER = int(os.environ.get("PROMETHEUS_METRICS_PORT_METRICS_UPDATER") or "8086")
PROMETHEUS_METRICS_PORT_DISK_USAGE_UPDATER = int(os.environ.get("PROMETHEUS_METRICS_PORT_DISK_USAGE_UPDATER") or "8087")
PROMETHEUS_METRICS_WITH_IDENTIFIER = os.environ.get("PROMETHEUS_METRICS_WITH_IDENTIFIER") == "yes"

DELETER_DEFAULT_DELETE_NAMESPACE = os.environ.get("DELETER_DEFAULT_DELETE_NAMESPACE") == "yes"
DELETER_DEFAULT_DELETE_HELM = (os.environ.get("DELETER_DEFAULT_DELETE_HELM") or "yes") == "yes"

DEPLOYER_USE_EXTERNAL_SERVICE = os.environ.get("DEPLOYER_USE_EXTERNAL_SERVICE") == "yes"
DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS = os.environ.get("DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS") == "yes"

DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "1")
UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = float(os.environ.get("UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "30")
FORCE_UPDATE_MAX_HOURS_TTL = float(os.environ.get("FORCE_UPDATE_MAX_HOURS_TTL") or "24")
FORCE_DELETE_GRACE_PERIOD_HOURS = float(os.environ.get("FORCE_DELETE_GRACE_PERIOD_HOURS") or "1")

LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS = int(os.environ.get("LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS") or "300")
METRICS_LOGGER_DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS = int(os.environ.get("METRICS_LOGGER_DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS") or "300")

METRICS_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = int(os.environ.get("METRICS_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "1")

FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES = int(os.environ.get('FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES') or '30')

WEB_UI_PORT = int(os.environ.get("WEB_UI_PORT") or '8182')

DISK_USAGE_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = int(os.environ.get("DISK_USAGE_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "30")
DISK_USAGE_UPDATER_NFS_SERVER = os.environ.get("DISK_USAGE_UPDATER_NFS_SERVER") or "cwm-nfs"
DISK_USAGE_UPDATER_NFS_ROOT_PATH = os.environ.get("DISK_USAGE_UPDATER_NFS_ROOT_PATH") or "/ganesha-ceph/eu-vobjstore001"

ALERTER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = int(os.environ.get("ALERTER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "15")
ALERTER_SLACK_WEBHOOK_URL = os.environ.get("ALERTER_SLACK_WEBHOOK_URL")
ALERTER_MESSAGE_PREFIX = os.environ.get("ALERTER_MESSAGE_PREFIX")

CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = int(os.environ.get("CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "300")

NODES_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = int(os.environ.get("NODES_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS") or "60")
DNS_RECORDS_PREFIX = os.environ.get("DNS_RECORDS_PREFIX") or "cwmc-operator-test"
AWS_ROUTE53_HOSTEDZONE_ID = os.environ.get("AWS_ROUTE53_HOSTEDZONE_ID") or ""
AWS_ROUTE53_HOSTEDZONE_DOMAIN = os.environ.get("AWS_ROUTE53_HOSTEDZONE_DOMAIN") or "example.com"

DUMMY_TEST_WORKER_ID = os.environ.get('DUMMY_TEST_WORKER_ID') or 'cwdummytst'
DUMMY_TEST_HOSTNAME = os.environ.get('DUMMY_TEST_HOSTNAME') or 'cwdummytst.example007.com'

MOCK_GATEWAYS = json.loads(os.environ.get('MOCK_GATEWAYS') or '{}')

DEPLOYER_WITH_HELM_DRY_RUN = os.environ.get('DEPLOYER_WITH_HELM_DRY_RUN') == 'yes'

CLEAR_CACHER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS = int(os.environ.get('CLEAR_CACHER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS') or '5')
