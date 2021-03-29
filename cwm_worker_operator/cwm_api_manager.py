from cwm_worker_operator.metrics_updater import DATEFORMAT
from cwm_worker_operator import common


CWM_DATEFORMAT = "%Y%m%d%H%M%S"


class CwmApiManager:

    def _do_send_agg_metrics(self, data):
        # TBD
        pass

    def get_utc_timestamp(self, t):
        return common.strptime(t, DATEFORMAT).strftime(CWM_DATEFORMAT)

    def get_measurements(self, measurements):
        return [{**m, 't': self.get_utc_timestamp(m['t'])} for m in measurements][:10]

    def send_agg_metrics(self, domain_name, minutes):
        self._do_send_agg_metrics({
            'domain_name': domain_name,
            'measurements': self.get_measurements(minutes)
        })
