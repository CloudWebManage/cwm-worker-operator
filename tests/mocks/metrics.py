from cwm_worker_operator.metrics import InitializerMetrics, DeployerMetrics, WaiterMetrics


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
