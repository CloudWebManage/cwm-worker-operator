import datetime

from prometheus_client import Histogram

from cwm_worker_operator import config


class BaseMetrics:

    def __init__(self):
        self._volume_config_fetch = Histogram('volume_config_fetch_latency', 'volume config fetch latency', ["domain", "status"])

    def cwm_api_volume_config_success_from_api(self, domain_name, start_time):
        self._volume_config_fetch.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                         "success").observe((datetime.datetime.now() - start_time).total_seconds())

    def cwm_api_volume_config_error_from_api(self, domain_name, start_time):
        self._volume_config_fetch.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                         "error").observe((datetime.datetime.now() - start_time).total_seconds())

    def cwm_api_volume_config_success_from_cache(self, domain_name, start_time):
        self._volume_config_fetch.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                         "success_cache").observe((datetime.datetime.now() - start_time).total_seconds())


class InitializerMetrics(BaseMetrics):

    def __init__(self):
        super(InitializerMetrics, self).__init__()
        self._initializer_request = Histogram('initializer_request_latency', 'initializer request latency', ["domain", "status"])

    def invalid_volume_zone(self, domain_name, start_time):
        self._initializer_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                         "invalid_volume_zone").observe((datetime.datetime.now() - start_time).total_seconds())

    def failed_to_get_volume_config(self, domain_name, start_time):
        self._initializer_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                         "failed_to_get_volume_config").observe((datetime.datetime.now() - start_time).total_seconds())

    def initialized(self, domain_name, start_time):
        self._initializer_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                         "initialized").observe((datetime.datetime.now() - start_time).total_seconds())


class DeployerMetrics(BaseMetrics):

    def __init__(self):
        super(DeployerMetrics, self).__init__()
        self._deployer_request = Histogram('deployer_request_latency', 'deployer request latency', ["domain", "status"])

    def deploy_success(self, domain_name, start_time):
        self._deployer_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                      "success").observe((datetime.datetime.now() - start_time).total_seconds())

    def deploy_failed(self, domain_name, start_time):
        self._deployer_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                      "failed").observe((datetime.datetime.now() - start_time).total_seconds())

    def failed_to_get_volume_config(self, domain_name, start_time):
        self._deployer_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                      "failed_to_get_volume_config").observe((datetime.datetime.now() - start_time).total_seconds())


class WaiterMetrics(BaseMetrics):

    def __init__(self):
        super(WaiterMetrics, self).__init__()
        self._waiter_request = Histogram('waiter_request_latency', 'waiter request latency', ["domain", "status"])

    def failed_to_get_volume_config(self, domain_name, start_time):
        self._waiter_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                    "failed_to_get_volume_config").observe((datetime.datetime.now() - start_time).total_seconds())

    def deployment_success(self, domain_name, start_time):
        self._waiter_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                    "success").observe((datetime.datetime.now() - start_time).total_seconds())

    def deployment_timeout(self, domain_name, start_time):
        self._waiter_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                    "timeout").observe((datetime.datetime.now() - start_time).total_seconds())


class DeleterMetrics(BaseMetrics):

    def __init__(self):
        super(DeleterMetrics, self).__init__()
        self._deleter_request = Histogram('deleter_request_latency', 'deleter request latency', ["domain", "status"])

    def delete_success(self, domain_name, start_time):
        self._deleter_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                     "success").observe((datetime.datetime.now() - start_time).total_seconds())

    def delete_failed(self, domain_name, start_time):
        self._deleter_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                     "failed").observe((datetime.datetime.now() - start_time).total_seconds())


class UpdaterMetrics(BaseMetrics):

    def __init__(self):
        super(UpdaterMetrics, self).__init__()
        self._updater_request = Histogram('updater_request_latency', 'updater request latency', ["domain", "status"])

    def not_deployed_force_update(self, domain_name, start_time):
        self._updater_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                     "not_deployed_force_update").observe((datetime.datetime.now() - start_time).total_seconds())

    def force_delete(self, domain_name, start_time):
        self._updater_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                     "force_delete").observe((datetime.datetime.now() - start_time).total_seconds())

    def force_update(self, domain_name, start_time):
        self._updater_request.labels(domain_name if config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL else "",
                                     "force_update").observe((datetime.datetime.now() - start_time).total_seconds())
