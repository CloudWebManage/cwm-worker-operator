from prometheus_client import Histogram

from cwm_worker_operator import config
from cwm_worker_operator import common


class BaseMetrics:

    def __init__(self):
        self._volume_config_fetch = Histogram('volume_config_fetch_latency', 'volume config fetch latency', ["worker_id", "status"])

    def _observe(self, histogram, identifier, start_time, status):
        histogram.labels(identifier if config.PROMETHEUS_METRICS_WITH_IDENTIFIER else "", status).observe((common.now() - start_time).total_seconds())

    def cwm_api_volume_config_success_from_api(self, worker_id, start_time):
        self._observe(self._volume_config_fetch, worker_id, start_time, "success")

    def cwm_api_volume_config_error_from_api(self, worker_id, start_time):
        self._observe(self._volume_config_fetch, worker_id, start_time, "error")

    def cwm_api_volume_config_success_from_cache(self, worker_id, start_time):
        self._observe(self._volume_config_fetch, worker_id, start_time, "success_cache")


class InitializerMetrics(BaseMetrics):

    def __init__(self):
        super(InitializerMetrics, self).__init__()
        self._initializer_request = Histogram('initializer_request_latency', 'initializer request latency (identifier=hostname for failed_to_get_volume_config, else worker_id)', ["identifier", "status"])

    def invalid_volume_zone(self, worker_id, start_time):
        self._observe(self._initializer_request, worker_id, start_time, "invalid_volume_zone")

    def invalid_hostname(self, worker_id, start_time):
        self._observe(self._initializer_request, worker_id, start_time, "invalid_hostname")

    def failed_to_get_volume_config(self, hostname, start_time):
        self._observe(self._initializer_request, hostname, start_time, "failed_to_get_volume_config")

    def initialized(self, worker_id, start_time):
        self._observe(self._initializer_request, worker_id, start_time, "initialized")

    def exception(self, worker_id, start_time):
        self._observe(self._initializer_request, worker_id, start_time, "exception")


class DeployerMetrics(BaseMetrics):

    def __init__(self):
        super(DeployerMetrics, self).__init__()
        self._deployer_request = Histogram('deployer_request_latency', 'deployer request latency', ["worker_id", "status"])

    def deploy_success(self, worker_id, start_time):
        self._observe(self._deployer_request, worker_id, start_time, "success")

    def deploy_failed(self, worker_id, start_time):
        self._observe(self._deployer_request, worker_id, start_time, "failed")

    def failed_to_get_volume_config(self, worker_id, start_time):
        self._observe(self._deployer_request, worker_id, start_time, "failed_to_get_volume_config")

    def exception(self, worker_id, start_time):
        self._observe(self._deployer_request, worker_id, start_time, "exception")


class WaiterMetrics(BaseMetrics):

    def __init__(self):
        super(WaiterMetrics, self).__init__()
        self._waiter_request = Histogram('waiter_request_latency', 'waiter request latency', ["worker_id", "status"])

    def failed_to_get_volume_config(self, worker_id, start_time):
        self._observe(self._waiter_request, worker_id, start_time, "failed_to_get_volume_config")

    def deployment_success(self, worker_id, start_time):
        self._observe(self._waiter_request, worker_id, start_time, "success")

    def deployment_timeout(self, worker_id, start_time):
        self._observe(self._waiter_request, worker_id, start_time, "timeout")

    def exception(self, worker_id, start_time):
        self._observe(self._waiter_request, worker_id, start_time, "exception")


class DeleterMetrics(BaseMetrics):

    def __init__(self):
        super(DeleterMetrics, self).__init__()
        self._deleter_request = Histogram('deleter_request_latency', 'deleter request latency', ["worker_id", "status"])

    def delete_success(self, worker_id, start_time):
        self._observe(self._deleter_request, worker_id, start_time, "success")

    def exception(self, worker_id, start_time):
        self._observe(self._deleter_request, worker_id, start_time, "exception")

    def delete_canceled(self, worker_id, start_time):
        self._observe(self._deleter_request, worker_id, start_time, "delete_canceled")


class UpdaterMetrics(BaseMetrics):

    def __init__(self):
        super(UpdaterMetrics, self).__init__()
        self._updater_request = Histogram('updater_request_latency', 'updater request latency', ["worker_id", "status"])

    def not_deployed_force_update(self, worker_id, start_time):
        self._observe(self._updater_request, worker_id, start_time, "not_deployed_force_update")

    def force_delete(self, worker_id, start_time):
        self._observe(self._updater_request, worker_id, start_time, "force_delete")

    def force_update(self, worker_id, start_time):
        self._observe(self._updater_request, worker_id, start_time, "force_update")

    def exception(self, worker_id, start_time):
        self._observe(self._updater_request, worker_id, start_time, "exception")


class MetricsUpdaterMetrics(BaseMetrics):

    def __init__(self):
        super(MetricsUpdaterMetrics, self).__init__()
        self._metrics_updater_request = Histogram('metrics_updater_request_latency', 'metrics updater request latency', ["worker_id", "status"])

    def exception(self, worker_id, start_time):
        self._observe(self._metrics_updater_request, worker_id, start_time, "exception")

    def agg_metrics_update(self, worker_id, start_time):
        self._observe(self._metrics_updater_request, worker_id, start_time, "agg_metrics_update")


class DiskUsageUpdaterMetrics(BaseMetrics):

    def __init__(self):
        super(DiskUsageUpdaterMetrics, self).__init__()
        self._disk_usage_updater_request = Histogram('disk_usage_updater_request_latency', 'disk usage updater request latency', ["worker_id", "status"])

    def exception(self, worker_id, start_time):
        self._observe(self._disk_usage_updater_request, worker_id, start_time, "exception")

    def disk_usage_update(self, worker_id, start_time):
        self._observe(self._disk_usage_updater_request, worker_id, start_time, "disk_usage_update")


class NasCheckerMetrics:

    def __init__(self):
        self._mount_duration = Histogram('nas_checker_mount_duration',
                                         'nas checker mount duration (seconds)',
                                         ["node_name", "nas_ip"])

    def observe_mount_duration(self, node_name, nas_ip, duration_seconds):
        self._mount_duration.labels(node_name, nas_ip).observe(duration_seconds)
