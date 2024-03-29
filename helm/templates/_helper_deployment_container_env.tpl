{{- define "deployment.container.env" }}
- name: CWM_API_URL
  valueFrom: {"secretKeyRef":{"name":"cwm-worker-operator", "key":"CWM_API_URL"}}
- name: CWM_API_KEY
  valueFrom: {"secretKeyRef":{"name":"cwm-worker-operator", "key":"CWM_API_KEY"}}
- name: CWM_API_SECRET
  valueFrom: {"secretKeyRef":{"name":"cwm-worker-operator", "key":"CWM_API_SECRET"}}
{{ if .root.Values.debug }}
- name: DEBUG
  value: "yes"
- name: DEBUG_VERBOSITY
  value: {{ .root.Values.debugVerbosity | quote }}
{{ end }}
- name: INGRESS_REDIS_HOST
  value: {{ .root.Values.operator.INGRESS_REDIS_HOST | quote }}
- name: INGRESS_REDIS_PORT
  value: {{ .root.Values.operator.INGRESS_REDIS_PORT | quote }}
- name: INGRESS_REDIS_POOL_MAX_CONNECTIONS
  value: {{ .root.Values.operator.INGRESS_REDIS_POOL_MAX_CONNECTIONS | quote }}
- name: INGRESS_REDIS_POOL_TIMEOUT
  value: {{ .root.Values.operator.INGRESS_REDIS_POOL_TIMEOUT | quote }}
- name: INGRESS_REDIS_DB
  value: {{ .root.Values.operator.INGRESS_REDIS_DB | quote }}
- name: INTERNAL_REDIS_HOST
  value: {{ .root.Values.operator.INTERNAL_REDIS_HOST | quote }}
- name: INTERNAL_REDIS_PORT
  value: {{ .root.Values.operator.INTERNAL_REDIS_PORT | quote }}
- name: INTERNAL_REDIS_POOL_MAX_CONNECTIONS
  value: {{ .root.Values.operator.INTERNAL_REDIS_POOL_MAX_CONNECTIONS | quote }}
- name: INTERNAL_REDIS_POOL_TIMEOUT
  value: {{ .root.Values.operator.INTERNAL_REDIS_POOL_TIMEOUT | quote }}
- name: INTERNAL_REDIS_DB
  value: {{ .root.Values.operator.INTERNAL_REDIS_DB | quote }}
- name: METRICS_REDIS_HOST
  value: {{ .root.Values.operator.METRICS_REDIS_HOST | quote }}
- name: METRICS_REDIS_PORT
  value: {{ .root.Values.operator.METRICS_REDIS_PORT | quote }}
- name: METRICS_REDIS_POOL_MAX_CONNECTIONS
  value: {{ .root.Values.operator.METRICS_REDIS_POOL_MAX_CONNECTIONS | quote }}
- name: METRICS_REDIS_POOL_TIMEOUT
  value: {{ .root.Values.operator.METRICS_REDIS_POOL_TIMEOUT | quote }}
- name: METRICS_REDIS_DB
  value: {{ .root.Values.operator.METRICS_REDIS_DB | quote }}
- name: CWM_ZONE
  value: {{ .root.Values.cwm_zone | quote }}
- name: CWM_ADDITIONAL_ZONES
  value: {{ .root.Values.cwm_additional_zones | quote }}
{{ if .root.Values.cwm_api_volume_config_version }}
- name: CWM_API_VOLUME_CONFIG_VERSION
  value: {{ .root.Values.cwm_api_volume_config_version | quote }}
{{ end }}
- name: INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.INITIALIZER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS
  value: {{ .root.Values.operator.DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS | quote }}
- name: DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.DEPLOYER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG_JSON
  value: {{ .root.Values.operator.CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG_JSON | quote }}
- name: MINIO_EXTRA_CONFIG_JSON
  value: {{ .root.Values.operator.MINIO_EXTRA_CONFIG_JSON | quote }}
- name: CWM_WORKER_EXTRA_OBJECTS_JSON
  value: {{ .root.Values.operator.CWM_WORKER_EXTRA_OBJECTS_JSON | quote }}
- name: CACHE_MINIO_VERSIONS
  value: {{ .root.Values.operator.CACHE_MINIO_VERSIONS | quote }}
- name: PROMETHEUS_METRICS_PORT_INITIALIZER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_INITIALIZER | quote }}
- name: PROMETHEUS_METRICS_PORT_DEPLOYER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_DEPLOYER | quote }}
- name: PROMETHEUS_METRICS_PORT_WAITER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_WAITER | quote }}
- name: PROMETHEUS_METRICS_PORT_UPDATER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_UPDATER | quote }}
- name: PROMETHEUS_METRICS_PORT_DELETER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_DELETER | quote }}
- name: PROMETHEUS_METRICS_PORT_METRICS_UPDATER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_METRICS_UPDATER | quote }}
- name: PROMETHEUS_METRICS_PORT_DISK_USAGE_UPDATER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_DISK_USAGE_UPDATER | quote }}
- name: PROMETHEUS_METRICS_PORT_NAS_CHECKER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_NAS_CHECKER | quote }}
- name: PROMETHEUS_METRICS_PORT_WORKERS_CHECKER
  value: {{ .root.Values.operator.PROMETHEUS_METRICS_PORT_WORKERS_CHECKER | quote }}
{{ if .root.Values.operator.PROMETHEUS_METRICS_WITH_IDENTIFIER }}
- name: PROMETHEUS_METRICS_WITH_IDENTIFIER
  value: "yes"
{{ end }}
- name: DELETER_DEFAULT_DELETE_NAMESPACE
  value: {{ if .root.Values.operator.DELETER_DEFAULT_DELETE_NAMESPACE }}"yes"{{ else }}"no"{{ end }}
- name: DELETER_DEFAULT_DELETE_HELM
  value: {{ if .root.Values.operator.DELETER_DEFAULT_DELETE_HELM }}"yes"{{ else }}"no"{{ end }}
- name: DELETER_DATA_DELETE_CONFIG_JSON
  value: {{ .root.Values.operator.DELETER_DATA_DELETE_CONFIG_JSON | quote }}
- name: DEPLOYER_USE_EXTERNAL_SERVICE
  value: {{ if .root.Values.operator.DEPLOYER_USE_EXTERNAL_SERVICE }}"yes"{{ else }}"no"{{ end }}
- name: DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS
  value: {{ if .root.Values.operator.DEPLOYER_USE_EXTERNAL_EXTRA_OBJECTS }}"yes"{{ else }}"no"{{ end }}
- name: DEPLOYER_MAX_ATTEMPT_NUMBERS
  value: {{ .root.Values.operator.DEPLOYER_MAX_ATTEMPT_NUMBERS | quote }}
- name: DEPLOYER_WAIT_DEPLOYMENT_ERROR_MAX_SECONDS
  value: {{ .root.Values.operator.DEPLOYER_WAIT_DEPLOYMENT_ERROR_MAX_SECONDS | quote }}
- name: DEPLOYER_MAX_PARALLEL_DEPLOY_PROCESSES
  value: {{ .root.Values.operator.DEPLOYER_MAX_PARALLEL_DEPLOY_PROCESSES | quote }}
- name: DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: FORCE_UPDATE_MAX_HOURS_TTL
  value: {{ .root.Values.operator.FORCE_UPDATE_MAX_HOURS_TTL | quote }}
- name: UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: WAITER_VERIFY_WORKER_ACCESS
  value: {{ if .root.Values.operator.WAITER_VERIFY_WORKER_ACCESS }}"yes"{{ else }}"no"{{ end }}
- name: WAITER_MAX_PARALLEL_DEPLOY_PROCESSES
  value: {{ .root.Values.operator.WAITER_MAX_PARALLEL_DEPLOY_PROCESSES | quote }}
- name: WORKER_ERROR_MAX_ATTEMPTS
  value: {{ .root.Values.operator.WORKER_ERROR_MAX_ATTEMPTS | quote }}
- name: FORCE_DELETE_GRACE_PERIOD_HOURS
  value: {{ .root.Values.operator.FORCE_DELETE_GRACE_PERIOD_HOURS | quote }}
- name: LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS
  value: {{ .root.Values.operator.LAST_ACTION_LOGGER_UPDATE_GRACE_PERIOD_SECONDS | quote }}
- name: METRICS_LOGGER_DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS
  value: {{ .root.Values.operator.METRICS_LOGGER_DEPLOYMENT_API_METRICS_FLUSH_INTERVAL_SECONDS | quote }}
- name: PROMETHEUS_URL
  value: {{ .root.Values.operator.PROMETHEUS_URL | quote }}
- name: METRICS_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.METRICS_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES
  value: {{ .root.Values.operator.FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES | quote }}
- name: WEB_UI_PORT
  value: {{ .root.Values.operator.WEB_UI_PORT | quote }}
- name: DISK_USAGE_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.DISK_USAGE_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: DISK_USAGE_UPDATER_NFS_SERVER
  value: {{ .root.Values.operator.DISK_USAGE_UPDATER_NFS_SERVER | quote }}
- name: DISK_USAGE_UPDATER_NFS_ROOT_PATH
  value: {{ .root.Values.operator.DISK_USAGE_UPDATER_NFS_ROOT_PATH | quote }}
- name: ALERTER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.ALERTER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: ALERTER_SLACK_WEBHOOK_URL
  value: {{ .root.Values.operator.ALERTER_SLACK_WEBHOOK_URL | quote }}
- name: ALERTER_MESSAGE_PREFIX
  value: {{ .root.Values.operator.ALERTER_MESSAGE_PREFIX | quote }}
- name: CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: NODES_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.NODES_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: DNS_RECORDS_PREFIX
  value: {{ .root.Values.operator.DNS_RECORDS_PREFIX | quote }}
{{ if eq $.deploymentName "nodes-checker" }}
- name: AWS_ACCESS_KEY_ID
  value: {{ .root.Values.operator.AWS_ACCESS_KEY_ID | quote }}
- name: AWS_SECRET_ACCESS_KEY
  value: {{ .root.Values.operator.AWS_SECRET_ACCESS_KEY | quote }}
- name: AWS_ROUTE53_HOSTEDZONE_ID
  value: {{ .root.Values.operator.AWS_ROUTE53_HOSTEDZONE_ID | quote }}
{{ end }}
- name: AWS_ROUTE53_HOSTEDZONE_DOMAIN
  value: {{ .root.Values.operator.AWS_ROUTE53_HOSTEDZONE_DOMAIN | quote }}
- name: DUMMY_TEST_WORKER_ID
  value: {{ .root.Values.operator.DUMMY_TEST_WORKER_ID | quote }}
- name: DUMMY_TEST_HOSTNAME
  value: {{ .root.Values.operator.DUMMY_TEST_HOSTNAME | quote }}
- name: MOCK_GATEWAYS
  value: {{ .root.Values.operator.MOCK_GATEWAYS | quote }}
- name: DEPLOYER_WITH_HELM_DRY_RUN
  value: {{ if .root.Values.operator.DEPLOYER_WITH_HELM_DRY_RUN }}"yes"{{ else }}"no"{{ end }}
- name: CLEAR_CACHER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.CLEAR_CACHER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: UPDATER_DEFAULT_LAST_UPDATE_DATETIME_SECONDS
  value: {{ .root.Values.operator.UPDATER_DEFAULT_LAST_UPDATE_DATETIME_SECONDS | quote }}
- name: UPDATER_MAX_PARALLEL_DEPLOY_PROCESSES
  value: {{ .root.Values.operator.UPDATER_MAX_PARALLEL_DEPLOY_PROCESSES | quote }}
- name: DHPARAM_KEY
  value: {{ .root.Values.operator.DHPARAM_KEY | quote }}
- name: VOLUME_CONFIG_OVERRIDE_URL
  value: {{ .root.Values.operator.VOLUME_CONFIG_OVERRIDE_URL | quote }}
- name: VOLUME_CONFIG_OVERRIDE_USERNAME
  value: {{ .root.Values.operator.VOLUME_CONFIG_OVERRIDE_USERNAME | quote }}
- name: VOLUME_CONFIG_OVERRIDE_PASSWORD
  value: {{ .root.Values.operator.VOLUME_CONFIG_OVERRIDE_PASSWORD | quote }}
- name: NAS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.NAS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: NAS_IPS
  value: {{ .root.Values.operator.NAS_IPS | quote }}
- name: NAS_CHECKER_VOLUME_TEMPLATE_JSON
  value: {{ .root.Values.operator.NAS_CHECKER_VOLUME_TEMPLATE_JSON | quote }}
- name: NAS_CHECKER_WITH_KUBELET_LOGS
  value: {{ if .root.Values.operator.NAS_CHECKER_WITH_KUBELET_LOGS }}"yes"{{ else }}"no"{{ end }}
- name: NAS_CHECKER_NAMESPACE
  value: {{ .root.Values.operator.NAS_CHECKER_NAMESPACE | quote }}
- name: LOCAL_STORAGE_PATH
  value: "/data"
- name: REDIS_CLEANER_DELETE_FAILED_TO_DEPLOY_HOSTNAME_ERROR_MIN_SECONDS
  value: {{ .root.Values.operator.REDIS_CLEANER_DELETE_FAILED_TO_DEPLOY_HOSTNAME_ERROR_MIN_SECONDS | quote }}
- name: REDIS_CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.REDIS_CLEANER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: REDIS_CLEANER_DELETE_ANY_HOSTNAME_ERROR_MIN_SECONDS
  value: {{ .root.Values.operator.REDIS_CLEANER_DELETE_ANY_HOSTNAME_ERROR_MIN_SECONDS | quote }}
- name: WORKERS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.WORKERS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: WORKERS_CHECKER_MAX_PARALLEL_DEPLOY_PROCESSES
  value: {{ .root.Values.operator.WORKERS_CHECKER_MAX_PARALLEL_DEPLOY_PROCESSES | quote }}
- name: WORKERS_CHECKER_ALERT_POD_PENDING_SECONDS
  value: {{ .root.Values.operator.WORKERS_CHECKER_ALERT_POD_PENDING_SECONDS | quote }}
- name: WORKERS_CHECKER_ALERT_POD_MISSING_SECONDS
  value: {{ .root.Values.operator.WORKERS_CHECKER_ALERT_POD_MISSING_SECONDS | quote }}
- name: WORKERS_CHECKER_ALERT_NAMESPACE_TERMINATING_SECONDS
  value: {{ .root.Values.operator.WORKERS_CHECKER_ALERT_NAMESPACE_TERMINATING_SECONDS | quote }}
- name: WORKERS_CHECKER_ALERT_INVALID_WORKER_SECONDS
  value: {{ .root.Values.operator.WORKERS_CHECKER_ALERT_INVALID_WORKER_SECONDS | quote }}
- name: THROTTLER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS
  value: {{ .root.Values.operator.THROTTLER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS | quote }}
- name: THROTTLER_THROTTLE_PERIOD_SECONDS
  value: {{ .root.Values.operator.THROTTLER_THROTTLE_PERIOD_SECONDS | quote }}
- name: THROTTLER_THROTTLE_MAX_REQUESTS
  value: {{ .root.Values.operator.THROTTLER_THROTTLE_MAX_REQUESTS | quote }}
- name: THROTTLER_CHECK_TTL_SECONDS
  value: {{ .root.Values.operator.THROTTLER_CHECK_TTL_SECONDS | quote }}
{{ .root.Values.operator.env }}
{{- end }}