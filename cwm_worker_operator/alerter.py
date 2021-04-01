import time
import json
import traceback

import requests

from cwm_worker_operator import config
from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig


def send_alert(alert_msg):
    if config.ALERTER_SLACK_WEBHOOK_URL:
        if config.ALERTER_MESSAGE_PREFIX:
            alert_msg = "{} {}".format(config.ALERTER_MESSAGE_PREFIX, alert_msg)
        res = requests.post(config.ALERTER_SLACK_WEBHOOK_URL, json={"text": alert_msg})
        res.raise_for_status()
    else:
        logs.debug_info("No slack webhook url!", alert_msg=alert_msg)


def process_cwm_worker_operator_logs_alert(alert, send_alert_callback):
    msg = alert.get('msg')
    kwargs = alert.get('kwargs') or {}
    send_alert_callback("operator-logs alert: {} ({})".format(msg, json.dumps(kwargs)))


def process_unknown_alert(alert, send_alert_callback):
    send_alert_callback("unknown operator alert: {}".format(json.dumps(alert)))


def process_alert(alert, send_alert_callback):
    if alert.get('type') == 'cwm-worker-operator-logs':
        process_cwm_worker_operator_logs_alert(alert, send_alert_callback)
    else:
        process_unknown_alert(alert, send_alert_callback)


def run_single_iteration(domains_config, send_alert_callback):
    while True:
        alert = domains_config.alerts_pop()
        if alert:
            try:
                process_alert(alert, send_alert_callback)
            except Exception as e:
                logs.debug_info("exception: {}".format(e), alert=alert)
                if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                    traceback.print_exc()
        else:
            break


def start_daemon(once=False, domains_config=None, send_alert_callback=None):
    if domains_config is None:
        domains_config = DomainsConfig()
    if send_alert_callback is None:
        send_alert_callback = send_alert
    while True:
        run_single_iteration(domains_config, send_alert_callback)
        if once:
            break
        time.sleep(config.ALERTER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
