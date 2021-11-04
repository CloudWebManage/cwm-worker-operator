import os
import json
import datetime
import traceback

import requests

from cwm_worker_operator import common
from cwm_worker_operator import config


CWM_DATEFORMAT = "%Y%m%d%H%M%S"


class CwmApiManager:

    def _do_send_agg_metrics(self, data):
        url = os.path.join(config.CWM_API_URL, 'svc', 'metrics', 'write')
        headers = {
            'AuthClientId': config.CWM_API_KEY,
            'AuthSecret': config.CWM_API_SECRET
        }
        res = requests.post(url, headers=headers, json=data)
        if res.status_code != 200:
            raise Exception("Failed to send agg metrics to CWM: {} {}".format(res.status_code, res.text))

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
            'storage_bytes': self.get_int_measurement(m, 'disk_usage_bytes'),
            'bytes_in': self.get_int_measurement(m, 'bytes_in'),
            'bytes_out': self.get_int_measurement(m, 'bytes_out'),
            'num_requests_in': self.get_int_measurement(m, 'num_requests_in'),
            'num_requests_out': self.get_int_measurement(m, 'num_requests_out'),
            'num_requests_misc': self.get_int_measurement(m, 'num_requests_misc'),
            "cpu_seconds": self.get_float_measurement(m, 'sum_cpu_seconds'),
            'ram_bytes': self.get_int_measurement(m, 'ram_limit_bytes')
        }

    def get_measurements(self, measurements):
        return [{**self.convert_measurements(m), 't': self.get_utc_timestamp(m['t'])} for m in measurements][:10]

    def send_agg_metrics(self, worker_id, minutes):
        self._do_send_agg_metrics({
            'instanceId': worker_id,
            'measurements': self.get_measurements(minutes)
        })

    def get_override_volume_config(self, volume_config):
        try:
            if not config.VOLUME_CONFIG_OVERRIDE_URL or not config.VOLUME_CONFIG_OVERRIDE_USERNAME or not config.VOLUME_CONFIG_OVERRIDE_PASSWORD:
                return {}
            worker_id = volume_config.get('instanceId')
            if not worker_id:
                return {}
            res = requests.get(
                '{}/{}.json'.format(config.VOLUME_CONFIG_OVERRIDE_URL, worker_id),
                auth=(config.VOLUME_CONFIG_OVERRIDE_USERNAME, config.VOLUME_CONFIG_OVERRIDE_PASSWORD),
                timeout=5
            )
            if res.status_code == 404:
                return {}
            elif res.status_code == 200:
                return res.json()
            else:
                raise Exception("Failed to get override config (status_code={})\n{}".format(res.status_code, res.text))
        except:
            if config.DEBUG:
                traceback.print_exc()
            return {}

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
        volume_config = json.loads(requests.get(url, headers=headers).text, strict=False)
        return common.dicts_merge(volume_config, self.get_override_volume_config(volume_config))

    def get_cwm_updates(self, from_datetime: datetime.datetime):
        url = '{}?from={}'.format(
            os.path.join(config.CWM_API_URL, 'svc', 'instances'),
            from_datetime.strftime('%Y-%m-%dT%H:%M:%S')
        )
        headers = {
            'AuthClientId': config.CWM_API_KEY,
            'AuthSecret': config.CWM_API_SECRET
        }
        for update in json.loads(requests.get(url, headers=headers).text, strict=False):
            yield {
                'worker_id': update['id'],
                'update_time': common.strptime(update['time'], '%Y-%m-%d %H:%M:%S')
            }
