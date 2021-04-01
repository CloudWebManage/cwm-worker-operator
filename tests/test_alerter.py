from cwm_worker_operator import alerter
from cwm_worker_operator import logs


def test_alerter(domains_config):
    sent_alerts = []

    def send_alert(alert_msg):
        sent_alerts.append(alert_msg)

    alerter.run_single_iteration(domains_config, send_alert)
    assert sent_alerts == []
    domains_config.alerts_push({"hello": "world"})
    logs.alert(domains_config, "Hello, world", foo="bar")
    alerter.run_single_iteration(domains_config, send_alert)
    assert sent_alerts == [
        'unknown operator alert: {"hello": "world"}',
        'operator-logs alert: Hello, world ({"foo": "bar"})',
    ]
