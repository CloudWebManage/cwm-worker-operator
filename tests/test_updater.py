import json
import datetime

import pytz

from cwm_worker_operator import updater
from cwm_worker_operator import config


def test_send_agg_metrics(domains_config, updater_metrics, cwm_api_manager):
    start_time = datetime.datetime.now()
    domain_name = 'example001.com'
    # metrics not sent to cwm because there are no agg metrics for domain
    updater.send_agg_metrics(domains_config, updater_metrics, domain_name, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []
    # aggregated metrics are sent to cwm
    with domains_config.get_redis() as r:
        r.set("worker:aggregated-metrics:{}".format(domain_name), json.dumps({
            'lu': "20210302030405",
            'm': [{'t': datetime.datetime(2021,3,2,1,2,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5000', 'bytes_out': '40000', 'num_requests_in': '1000', 'num_requests_out': '7000', 'num_requests_misc': '500', "cpu_seconds": "1234.5", "ram_bytes": "5678"},
                  {'t': datetime.datetime(2021,3,2,1,3,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5120', 'bytes_out': '41300', 'num_requests_in': '1120', 'num_requests_out': '7230', 'num_requests_misc': '503', "cpu_seconds": "2334.5", "ram_bytes": "5766"},
                  {'t': datetime.datetime(2021,3,2,1,4,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513', "cpu_seconds": "4334.5", "ram_bytes": "5987"}]
        }))
    updater.send_agg_metrics(domains_config, updater_metrics, domain_name, start_time, cwm_api_manager)

    assert cwm_api_manager.mock_calls_log == [
        ('_do_send_agg_metrics', {
            'domain_name': 'example001.com',
            'measurements': [{'t': datetime.datetime(2021,3,2,1,2,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5000', 'bytes_out': '40000', 'num_requests_in': '1000', 'num_requests_out': '7000', 'num_requests_misc': '500', "cpu_seconds": "1234.5", "ram_bytes": "5678"},
                             {'t': datetime.datetime(2021,3,2,1,3,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5120', 'bytes_out': '41300', 'num_requests_in': '1120', 'num_requests_out': '7230', 'num_requests_misc': '503', "cpu_seconds": "2334.5", "ram_bytes": "5766"},
                             {'t': datetime.datetime(2021,3,2,1,4,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513', "cpu_seconds": "4334.5", "ram_bytes": "5987"}]})
    ]
    # metrics not sent because less than 60 seconds since last send
    cwm_api_manager.mock_calls_log = []
    updater.send_agg_metrics(domains_config, updater_metrics, domain_name, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []
    # metrics not sent because last_update is the same as in previous send
    with domains_config.get_redis() as r:
        last_sent_update = (datetime.datetime.now() - datetime.timedelta(seconds=61)).strftime('%Y%m%d%H%M%S')
        last_update = "20210302030405"
        r.set('worker:aggregated-metrics-last-sent-update:{}'.format(domain_name), '{},{}'.format(last_sent_update, last_update))
    updater.send_agg_metrics(domains_config, updater_metrics, domain_name, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []


def test_updater_daemon(domains_config, deployments_manager, updater_metrics, cwm_api_manager):
    config.PROMETHEUS_METRICS_WITH_DOMAIN_LABEL = True
    updated_more_then_half_hour_ago = (datetime.datetime.now() - datetime.timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
    updated_less_then_half_hour_ago = (datetime.datetime.now() - datetime.timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    updated_less_then_day_ago = (datetime.datetime.now() - datetime.timedelta(hours=23)).strftime("%Y-%m-%d %H:%M:%S")
    updated_more_then_day_ago = (datetime.datetime.now() - datetime.timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    updated_less_then_hour_ago = (datetime.datetime.now() - datetime.timedelta(minutes=55)).strftime("%Y-%m-%d %H:%M:%S")
    updated_more_then_hour_ago = (datetime.datetime.now() - datetime.timedelta(minutes=65)).strftime("%Y-%m-%d %H:%M:%S")
    deployments_manager.all_releases += [
        # deployment still pending after more then half hour in revision 1 or 2 is forced to update again
        {
            "namespace": "pending--old--revision1",
            "updated": updated_more_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 1
        },
        {
            "namespace": "pending--old--revision2",
            "updated": updated_more_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 2
        },
        # deployment still pending after more then half hour in bigger revision is left as-is (no point retrying continuously)
        {
            "namespace": "pending--old--revision3",
            "updated": updated_more_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 3
        },
        # deployment still pending after less then half hour in revision <=2 is left as-is (we give a half-hour in pending before retrying)
        {
            "namespace": "pending--old--revision2",
            "updated": updated_less_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 2
        },
        # deployed worker updated more then hour ago with no action for last 30 minutes is marked for deletion
        {
            "namespace": "deployed--no--action",
            "updated": updated_more_then_hour_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
        # deployed worker with last action in last 30 minutes and updated less then 24 hours ago is left as-is
        {
            "namespace": "deployed--has--action--recent-update",
            "updated": updated_less_then_day_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
        # deployed worker with last action in last 30 minutes and update more then 24 hours ago is forced to update
        {
            "namespace": "deployed--has--action--old-update",
            "updated": updated_more_then_day_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
        # deployed worker updated less then hour ago with no last action is left as-is (give time to get some action)
        {
            "namespace": "deployed--no--action--recent-update",
            "updated": updated_less_then_hour_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
    ]
    with domains_config.get_redis() as r:
        for namespace_name, last_action in {
            "deployed--has--action--recent-update": datetime.datetime.now() - datetime.timedelta(minutes=25),
            "deployed--has--action--old-update": datetime.datetime.now() - datetime.timedelta(minutes=25)
        }.items():
            r.set('deploymentid:last_action:{}:http'.format(namespace_name), (last_action - datetime.timedelta(minutes=2)).strftime("%Y%m%dT%H%M%S"))
            r.set('deploymentid:last_action:{}:https'.format(namespace_name), last_action.strftime("%Y%m%dT%H%M%S"))
        r.set("worker:aggregated-metrics:deployed.has.action.recent-update", json.dumps({
            'lu': "20210302030405",
            'm': [
                {'t': datetime.datetime(2021,3,2,1,2,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5000', 'bytes_out': '40000', 'num_requests_in': '1000', 'num_requests_out': '7000', 'num_requests_misc': '500', "cpu_seconds": "1234.5", "ram_bytes": "5678"},
                {'t': datetime.datetime(2021,3,2,1,3,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5120', 'bytes_out': '41300', 'num_requests_in': '1120', 'num_requests_out': '7230', 'num_requests_misc': '503', "cpu_seconds": "2334.5", "ram_bytes": "5766"},
                {'t': datetime.datetime(2021,3,2,1,4,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513', "cpu_seconds": "4334.5", "ram_bytes": "5987"},
            ]
        }))
        r.set("worker:aggregated-metrics:deployed.has.action.old-update", json.dumps({
            'lu': "20210302030405",
            'm': [
                {'t': datetime.datetime(2021,3,2,3,1,15).strftime('%Y%m%d%H%M%S'),                                           'num_requests_in': '1000', 'num_requests_out': '7000',                           },
                {'t': datetime.datetime(2021,3,2,3,1,33).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5120', 'bytes_out': '45000',                            'num_requests_out': '6930',                           },
                {'t': datetime.datetime(2021,3,2,3,4,5).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513'},
            ]
        }))
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
    assert [o['labels'] for o in updater_metrics.observations] == [
        ('pending.old.revision1', 'not_deployed_force_update'),
        ('pending.old.revision2', 'not_deployed_force_update'),
        ('deployed.no.action', 'force_delete'),
        ('deployed.has.action.old-update', 'force_update'),
    ]
    with domains_config.get_redis() as r:
        force_update_domains = [key.decode().replace('worker:force_update:', '') for key in r.keys('worker:force_update:*')]
        force_delete_domains = [key.decode().replace('worker:force_delete:', '') for key in r.keys('worker:force_delete:*')]
        assert "pending.old.revision1" in force_update_domains
        assert "pending.old.revision2" in force_update_domains
        assert "deployed.has.action.old-update" in force_update_domains
        assert "deployed.no.action" in force_delete_domains
    assert cwm_api_manager.mock_calls_log == [
        ('_do_send_agg_metrics', {
            "domain_name": "deployed.has.action.recent-update",
            "measurements": [
                {"t": datetime.datetime(2021,3,2,1,2,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), "bytes_in": "5000", "bytes_out": "40000", "num_requests_in": "1000", "num_requests_out": "7000", "num_requests_misc": "500", "cpu_seconds": "1234.5", "ram_bytes": "5678"},
                {"t": datetime.datetime(2021,3,2,1,3,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), "bytes_in": "5120", "bytes_out": "41300", "num_requests_in": "1120", "num_requests_out": "7230", "num_requests_misc": "503", "cpu_seconds": "2334.5", "ram_bytes": "5766"},
                {"t": datetime.datetime(2021,3,2,1,4,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), "bytes_in": "5180", "bytes_out": "42200", "num_requests_in": "1280", "num_requests_out": "7680", "num_requests_misc": "513", "cpu_seconds": "4334.5", "ram_bytes": "5987"},
            ]
        }),
        ('_do_send_agg_metrics', {
            'domain_name': 'deployed.has.action.old-update',
            'measurements': [
                {'t': datetime.datetime(2021,3,2,3,1,15).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'),                                           'num_requests_in': '1000', 'num_requests_out': '7000',                           },
                {'t': datetime.datetime(2021,3,2,3,1,33).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5120', 'bytes_out': '45000',                            'num_requests_out': '6930',                           },
                {'t': datetime.datetime(2021,3,2,3,4,5).astimezone(pytz.UTC).strftime('%Y%m%d%H%M%S'), 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513'},
            ]
        })
    ]
    print("Starting 2nd run_single_iteration")
    cwm_api_manager.mock_calls_log = []
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []
