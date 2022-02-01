"""
Sends alerts (to Slack)
"""
import json
import traceback

import requests

from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon


class SendAlertsThrottle:

    def __init__(self, send_alert_callback):
        self.send_alert = send_alert_callback
        self.last_sent_alert = None
        self.last_sent_throttle_alert = None

    def process_alert(self, alert):
        if self.last_sent_alert is None or (common.now() - self.last_sent_alert).total_seconds() >= 120:
            self.last_sent_alert = common.now()
            return True
        else:
            if self.last_sent_throttle_alert is None or (common.now() - self.last_sent_throttle_alert).total_seconds() >= 120:
                self.last_sent_throttle_alert = common.now()
                self.send_alert("too many alerts, check cwm-worker-operator logs")
            return False


def send_alert(alert_msg):
    if config.ALERTER_SLACK_WEBHOOK_URL:
        if config.ALERTER_MESSAGE_PREFIX:
            alert_msg = "{} {}".format(config.ALERTER_MESSAGE_PREFIX, alert_msg)
        res = requests.post(config.ALERTER_SLACK_WEBHOOK_URL, json={"text": alert_msg}, timeout=15)
        res.raise_for_status()
    else:
        logs.debug_info("No slack webhook url!", alert_msg=alert_msg)


def process_cwm_worker_operator_logs_alert(alert, send_alert_callback):
    msg = alert.get('msg')
    kwargs = alert.get('kwargs') or {}
    send_alert_callback("operator-logs alert: {} ({})".format(msg, json.dumps(kwargs)))


def process_unknown_alert(alert, send_alert_callback):
    send_alert_callback("unknown operator alert: {}".format(json.dumps(alert)))


def process_alert(alert, send_alert_callback, send_alerts_throttle):
    if send_alerts_throttle.process_alert(alert):
        if alert.get('type') == 'cwm-worker-operator-logs':
            process_cwm_worker_operator_logs_alert(alert, send_alert_callback)
        else:
            process_unknown_alert(alert, send_alert_callback)


def run_single_iteration(domains_config, send_alert_callback, send_alerts_throttle, **_):
    while True:
        alert = domains_config.alerts_pop()
        if alert:
            try:
                process_alert(alert, send_alert_callback, send_alerts_throttle)
            except Exception as e:
                logs.debug_info("exception: {}".format(e), alert=alert)
                if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                    traceback.print_exc()
        else:
            break


def start_daemon(once=False, domains_config=None, send_alert_callback=None):
    if send_alert_callback is None:
        send_alert_callback = send_alert
    send_alerts_throttle = SendAlertsThrottle(send_alert_callback)
    Daemon(
        name='alerter',
        sleep_time_between_iterations_seconds=config.ALERTER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        run_single_iteration_extra_kwargs={'send_alert_callback': send_alert_callback,
                                           'send_alerts_throttle': send_alerts_throttle}
    ).start(once=once, with_prometheus=False)
