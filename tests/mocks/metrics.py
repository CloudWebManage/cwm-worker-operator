from cwm_worker_operator.metrics import (
    InitializerMetrics, DeployerMetrics, WaiterMetrics, DeleterMetrics, UpdaterMetrics,
    MetricsUpdaterMetrics, DiskUsageUpdaterMetrics
)


class MockHistogramLabels:

    def __init__(self, metrics, labels):
        self.metrics = metrics
        self.labels = labels

    def observe(self, value):
        self.metrics.observe(self.labels, value)


class MockHistogram:

    def __init__(self, metrics):
        self.metrics = metrics

    def labels(self, *labels):
        return MockHistogramLabels(self.metrics, labels)


class MockInitializerMetrics(InitializerMetrics):

    def __init__(self):
        self._initializer_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})


class MockDeployerMetrics(DeployerMetrics):

    def __init__(self):
        self._deployer_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})


class MockWaiterMetrics(WaiterMetrics):

    def __init__(self):
        self._waiter_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})


class MockDeleterMetrics(DeleterMetrics):

    def __init__(self):
        self._deleter_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})


class MockUpdaterMetrics(UpdaterMetrics):

    def __init__(self):
        self._updater_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})


class MockMetricsUpdaterMetrics(MetricsUpdaterMetrics):

    def __init__(self):
        self._metrics_updater_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})


class MockDiskUsageUpdaterMetrics(DiskUsageUpdaterMetrics):

    def __init__(self):
        self._disk_usage_updater_request = MockHistogram(self)
        self._volume_config_fetch = MockHistogram(self)
        self.observations = []

    def observe(self, labels, value):
        self.observations.append({'labels': labels, 'value': value})
