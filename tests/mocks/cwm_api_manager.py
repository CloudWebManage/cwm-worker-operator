from cwm_worker_operator.cwm_api_manager import CwmApiManager


class MockCwmApiManager(CwmApiManager):

    def __init__(self):
        self.mock_calls_log = []
        self.mock_cwm_updates = []
        self.mock_volume_config_api_calls = {}

    def _do_send_agg_metrics(self, data):
        self.mock_calls_log.append(('_do_send_agg_metrics', data))

    def get_cwm_updates(self, from_datetime):
        self.mock_calls_log.append(('get_cwm_updates', from_datetime))
        return self.mock_cwm_updates

    def volume_config_api_call(self, query_param, query_value):
        return self.mock_volume_config_api_calls['{}={}'.format(query_param, query_value)]
