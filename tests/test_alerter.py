from cwm_worker_operator import alerter
from cwm_worker_operator import logs


def test_alerter(domains_config):
    sent_alerts = []

    def send_alert(alert_msg):
        sent_alerts.append(alert_msg)

    send_alerts_throttle = alerter.SendAlertsThrottle(send_alert)

    alerter.run_single_iteration(domains_config, send_alert, send_alerts_throttle)
    assert sent_alerts == []
    domains_config.alerts_push({"hello": "world"})
    logs.alert(domains_config, "Hello, world", foo="bar")
    alerter.run_single_iteration(domains_config, send_alert, send_alerts_throttle)
    assert sent_alerts == [
        'unknown operator alert: {"hello": "world"}',
        'too many alerts, check cwm-worker-operator logs',
    ]
