import os
import json

import requests

from cwm_worker_operator import common
from cwm_worker_operator import config


CWM_DATEFORMAT = "%Y%m%d%H%M%S"


class CwmApiManager:

    def _do_send_agg_metrics(self, data):
        # TBD
        pass

    def get_utc_timestamp(self, t):
        from cwm_worker_operator.metrics_updater import DATEFORMAT
        return common.strptime(t, DATEFORMAT).strftime(CWM_DATEFORMAT)

    def get_gib_measurement(self, m, key):
        try:
            return common.bytes_to_gib(float(m.get(key) or 0.0))
        except:
            return 0.0

    def get_int_measurement(self, m, key):
        try:
            return int(m.get(key) or 0)
        except:
            return 0

    def get_float_measurement(self, m, key):
        try:
            return float(m.get(key) or 0.0)
        except:
            return 0.0

    def convert_measurements(self, m):
        return {
            'disk_usage_bytes': self.get_int_measurement(m, 'disk_usage_bytes'),
            'bytes_in': self.get_int_measurement(m, 'bytes_in'),
            'bytes_out': self.get_int_measurement(m, 'bytes_out'),
            'num_requests_in': self.get_int_measurement(m, 'num_requests_in'),
            'num_requests_out': self.get_int_measurement(m, 'num_requests_out'),
            'num_requests_misc': self.get_int_measurement(m, 'num_requests_misc'),
            "cpu_seconds": self.get_float_measurement(m, 'sum_cpu_seconds'),
            'ram_gib': self.get_gib_measurement(m, 'ram_limit_bytes')
        }

    def get_measurements(self, measurements):
        return [{**self.convert_measurements(m), 't': self.get_utc_timestamp(m['t'])} for m in measurements][:10]

    def send_agg_metrics(self, worker_id, minutes):
        self._do_send_agg_metrics({
            'instance_id': worker_id,
            'measurements': self.get_measurements(minutes)
        })

    def volume_config_api_call(self, query_param, query_value):
        url = "{}?{}={}".format(
            os.path.join(config.CWM_API_URL, 'svc', 'instances', 'getConfiguration'),
            query_param, query_value
        )
        # print(url)
        headers = {
            'AuthClientId': config.CWM_API_KEY,
            'AuthSecret': config.CWM_API_SECRET
        }
        return json.loads(requests.get(url, headers=headers).text, strict=False)
