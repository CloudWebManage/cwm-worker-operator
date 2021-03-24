import pytz
import datetime

from prometheus_client import Histogram

from cwm_worker_operator import config


class BaseMetrics:

    def __init__(self):
        self._volume_config_fetch = Histogram('volume_config_fetch_latency', 'volume config fetch latency', ["domain", "status"])

    def _observe(self, histogram, domain, start_time, status):
        histogram.labels(domain if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                         status).observe((datetime.datetime.now(pytz.UTC) - start_time).total_seconds())

    def cwm_api_volume_config_success_from_api(self, domain_name, start_time):
        self._observe(self._volume_config_fetch, domain_name, start_time, "success")

    def cwm_api_volume_config_error_from_api(self, domain_name, start_time):
        self._observe(self._volume_config_fetch, domain_name, start_time, "error")

    def cwm_api_volume_config_success_from_cache(self, domain_name, start_time):
        self._observe(self._volume_config_fetch, domain_name, start_time, "success_cache")


class InitializerMetrics(BaseMetrics):

    def __init__(self):
        super(InitializerMetrics, self).__init__()
        self._initializer_request = Histogram('initializer_request_latency', 'initializer request latency', ["domain", "status"])

    def invalid_volume_zone(self, domain_name, start_time):
        self._observe(self._initializer_request, domain_name, start_time, "invalid_volume_zone")

    def failed_to_get_volume_config(self, domain_name, start_time):
        self._observe(self._initializer_request, domain_name, start_time, "failed_to_get_volume_config")

    def initialized(self, domain_name, start_time):
        self._observe(self._initializer_request, domain_name, start_time, "initialized")

    def exception(self, domain_name, start_time):
        self._observe(self._initializer_request, domain_name, start_time, "exception")


class DeployerMetrics(BaseMetrics):

    def __init__(self):
        super(DeployerMetrics, self).__init__()
        self._deployer_request = Histogram('deployer_request_latency', 'deployer request latency', ["domain", "status"])

    def deploy_success(self, domain_name, start_time):
        self._observe(self._deployer_request, domain_name, start_time, "success")

    def deploy_failed(self, domain_name, start_time):
        self._observe(self._deployer_request, domain_name, start_time, "failed")

    def failed_to_get_volume_config(self, domain_name, start_time):
        self._observe(self._deployer_request, domain_name, start_time, "failed_to_get_volume_config")

    def exception(self, domain_name, start_time):
        self._observe(self._deployer_request, domain_name, start_time, "exception")


class WaiterMetrics(BaseMetrics):

    def __init__(self):
        super(WaiterMetrics, self).__init__()
        self._waiter_request = Histogram('waiter_request_latency', 'waiter request latency', ["domain", "status"])

    def failed_to_get_volume_config(self, domain_name, start_time):
        self._observe(self._waiter_request, domain_name, start_time, "failed_to_get_volume_config")

    def deployment_success(self, domain_name, start_time):
        self._observe(self._waiter_request, domain_name, start_time, "success")

    def deployment_timeout(self, domain_name, start_time):
        self._observe(self._waiter_request, domain_name, start_time, "timeout")

    def exception(self, domain_name, start_time):
        self._observe(self._waiter_request, domain_name, start_time, "exception")


class DeleterMetrics(BaseMetrics):

    def __init__(self):
        super(DeleterMetrics, self).__init__()
        self._deleter_request = Histogram('deleter_request_latency', 'deleter request latency', ["domain", "status"])

    def delete_success(self, domain_name, start_time):
        self._observe(self._deleter_request, domain_name, start_time, "success")

    def exception(self, domain_name, start_time):
        self._observe(self._deleter_request, domain_name, start_time, "exception")


class UpdaterMetrics(BaseMetrics):

    def __init__(self):
        super(UpdaterMetrics, self).__init__()
        self._updater_request = Histogram('updater_request_latency', 'updater request latency', ["domain", "status"])

    def not_deployed_force_update(self, domain_name, start_time):
        self._observe(self._updater_request, domain_name, start_time, "not_deployed_force_update")

    def force_delete(self, domain_name, start_time):
        self._observe(self._updater_request, domain_name, start_time, "force_delete")

    def force_update(self, domain_name, start_time):
        self._observe(self._updater_request, domain_name, start_time, "force_update")

    def exception(self, domain_name, start_time):
        self._observe(self._updater_request, domain_name, start_time, "exception")


class MetricsUpdaterMetrics(BaseMetrics):

    def __init__(self):
        super(MetricsUpdaterMetrics, self).__init__()
        self._metrics_updater_request = Histogram('metrics_updater_request_latency', 'metrics updater request latency', ["domain", "status"])

    def exception(self, domain_name, start_time):
        self._observe(self._metrics_updater_request, domain_name, start_time, "exception")

    def agg_metrics_update(self, domain_name, start_time):
        self._observe(self._metrics_updater_request, domain_name, start_time, "agg_metrics_update")
