from cwm_worker_operator.cwm_api_manager import CwmApiManager


class MockCwmApiManager(CwmApiManager):

    def __init__(self):
        self.mock_calls_log = []

    def _do_send_agg_metrics(self, data):
        self.mock_calls_log.append(('_do_send_agg_metrics', data))
