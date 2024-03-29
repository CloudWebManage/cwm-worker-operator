import json
import datetime

import pytz

from cwm_worker_operator import updater
from cwm_worker_operator import config
from cwm_worker_operator import common
from cwm_worker_operator.common import bytes_to_gib, now, get_namespace_name_from_worker_id


def test_send_agg_metrics(domains_config, updater_metrics, cwm_api_manager):
    start_time = now()
    worker_id = 'worker1'
    # metrics not sent to cwm because there are no agg metrics for domain
    updater.send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []
    # aggregated metrics are sent to cwm
    t1 = datetime.datetime(2021,3,2,1,2,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
    t2 = datetime.datetime(2021,3,2,1,3,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
    t3 = datetime.datetime(2021,3,2,1,4,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
    domains_config.keys.worker_aggregated_metrics.set(worker_id, json.dumps({
        'lu': t3,
        'm': [{'t': t1, 'disk_usage_bytes': 23911,
               'bytes_in': '50000000000', 'bytes_out': '400000000000', 'num_requests_in': '1000', 'num_requests_out': '7000', 'num_requests_misc': '500',
               "sum_cpu_seconds": "1234.5", "avg_ram_bytes_usage": "5678",
               'ram_requests_bytes': 510404200, 'ram_limit_bytes': 579404200},
              {'t': t2, 'disk_usage_bytes': 53955,
               'bytes_in': '51200000000', 'bytes_out': '413000000000', 'num_requests_in': '1120', 'num_requests_out': '7230', 'num_requests_misc': '503',
               "sum_cpu_seconds": "1098.3", "avg_ram_bytes_usage": "432",
               'ram_requests_bytes': 510404200, 'ram_limit_bytes': 579404200},
              {'t': t3, 'disk_usage_bytes': 9344,
               'bytes_in': '51800000000', 'bytes_out': '422000000000', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513',
               "sum_cpu_seconds": "2338.9", "avg_ram_bytes_usage": "0",
               'ram_requests_bytes': 0, 'ram_limit_bytes': 0}]
    }))
    updater.send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == [
        ('_do_send_agg_metrics', {
            'instanceId': worker_id,
            'measurements': [{'t': t1, 'storage_bytes': 23911,
                              'bytes_in': 50000000000, 'bytes_out': 400000000000, 'num_requests_in': 1000, 'num_requests_out': 7000, 'num_requests_misc': 500,
                              "cpu_seconds": 1234.5, 'ram_bytes': 579404200},
                             {'t': t2, 'storage_bytes': 53955,
                              'bytes_in': 51200000000, 'bytes_out': 413000000000, 'num_requests_in': 1120, 'num_requests_out': 7230, 'num_requests_misc': 503,
                              "cpu_seconds": 1098.3, 'ram_bytes': 579404200},
                             {'t': t3, 'storage_bytes': 9344,
                              'bytes_in': 51800000000, 'bytes_out': 422000000000, 'num_requests_in': 1280, 'num_requests_out': 7680, 'num_requests_misc': 513,
                              "cpu_seconds": 2338.9, 'ram_bytes': 0}]})
    ]
    # metrics not sent because less than 60 seconds since last send
    cwm_api_manager.mock_calls_log = []
    updater.send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []
    # metrics not sent because last_update is the same as in previous send
    last_sent_update = (now() - datetime.timedelta(seconds=61)).strftime('%Y%m%d%H%M%S')
    last_update = t3
    domains_config.keys.worker_aggregated_metrics_last_sent_update.set(worker_id, '{},{}'.format(last_sent_update, last_update))
    updater.send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager)
    assert cwm_api_manager.mock_calls_log == []


def test_updater_daemon(domains_config, deployments_manager, updater_metrics, cwm_api_manager):
    config.PROMETHEUS_METRICS_WITH_IDENTIFIER = True
    updated_more_then_half_hour_ago = (now() - datetime.timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
    updated_less_then_half_hour_ago = (now() - datetime.timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    updated_less_then_day_ago = (now() - datetime.timedelta(hours=23)).strftime("%Y-%m-%d %H:%M:%S")
    updated_more_then_day_ago = (now() - datetime.timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    updated_less_then_hour_ago = (now() - datetime.timedelta(minutes=55)).strftime("%Y-%m-%d %H:%M:%S")
    updated_more_then_hour_ago = (now() - datetime.timedelta(minutes=65)).strftime("%Y-%m-%d %H:%M:%S")
    worker_id_pending_old_revision1 = 'worker1'
    namespace_name_pending_old_revision1 = get_namespace_name_from_worker_id(worker_id_pending_old_revision1)
    worker_id_pending_old_revision2 = 'worker2'
    namespace_name_pending_old_revision2 = get_namespace_name_from_worker_id(worker_id_pending_old_revision2)
    worker_id_pending_old_revision3 = 'worker3'
    namespace_name_pending_old_revision3 = get_namespace_name_from_worker_id(worker_id_pending_old_revision3)
    worker_id_deployed_no_action = 'worker4'
    namespace_name_deployed_no_action = get_namespace_name_from_worker_id(worker_id_deployed_no_action)
    worker_id_deployed_has_action_recent_update = 'worker5'
    namespace_name_deployed_has_action_recent_update = get_namespace_name_from_worker_id(worker_id_deployed_has_action_recent_update)
    worker_id_deployed_has_action_old_update = 'worker6'
    namespace_name_deployed_has_action_old_update = get_namespace_name_from_worker_id(worker_id_deployed_has_action_old_update)
    worker_id_deployed_no_action_recent_update = 'worker7'
    namespace_name_deployed_no_action_recent_update = get_namespace_name_from_worker_id(worker_id_deployed_no_action_recent_update)
    deployments_manager.all_releases += [
        # deployment still pending after more then half hour in revision 1 or 2 is forced to update again
        {
            "namespace": namespace_name_pending_old_revision1,
            "updated": updated_more_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 1
        },
        {
            "namespace": namespace_name_pending_old_revision2,
            "updated": updated_more_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 2
        },
        # deployment still pending after more then half hour in bigger revision is left as-is (no point retrying continuously)
        {
            "namespace": namespace_name_pending_old_revision3,
            "updated": updated_more_then_half_hour_ago,
            "status": "pending",
            "app_version": "",
            "revision": 3
        },
        # TODO: this namespace already appears before, need to figure out what was meant by this test
        # deployment still pending after less then half hour in revision <=2 is left as-is (we give a half-hour in pending before retrying)
        # {
        #     "namespace": namespace_name_pending_old_revision2,
        #     "updated": updated_less_then_half_hour_ago,
        #     "status": "pending",
        #     "app_version": "",
        #     "revision": 2
        # },
        # deployed worker updated more then hour ago with no action for last 30 minutes is marked for deletion
        {
            "namespace": namespace_name_deployed_no_action,
            "updated": updated_more_then_hour_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
        # deployed worker with last action in last 30 minutes and updated less then 24 hours ago is left as-is
        {
            "namespace": namespace_name_deployed_has_action_recent_update,
            "updated": updated_less_then_day_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
        # deployed worker with last action in last 30 minutes and update more then 24 hours ago is forced to update
        {
            "namespace": namespace_name_deployed_has_action_old_update,
            "updated": updated_more_then_day_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
        # deployed worker updated less then hour ago with no last action is left as-is (give time to get some action)
        {
            "namespace": namespace_name_deployed_no_action_recent_update,
            "updated": updated_less_then_hour_ago,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        },
    ]
    with domains_config.get_metrics_redis() as r:
        for namespace_name, last_action in {
            namespace_name_deployed_has_action_recent_update: now() - datetime.timedelta(minutes=25),
            namespace_name_deployed_has_action_old_update: now() - datetime.timedelta(minutes=25)
        }.items():
            r.set('deploymentid:last_action:{}'.format(namespace_name), last_action.strftime("%Y%m%dT%H%M%S"))
        recent_update_t1 = datetime.datetime(2021,3,2,1,2,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        recent_update_t2 = datetime.datetime(2021,3,2,1,3,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        recent_update_t3 = datetime.datetime(2021,3,2,1,4,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        domains_config.keys.worker_aggregated_metrics.set(worker_id_deployed_has_action_recent_update, json.dumps({
            'lu': "20210302030405",
            'm': [
                {'t': recent_update_t1, 'disk_usage_bytes': '1234',
                 'bytes_in': '5000', 'bytes_out': '40000', 'num_requests_in': '1000', 'num_requests_out': '7000', 'num_requests_misc': '500',
                 "sum_cpu_seconds": "1234.5", "ram_limit_bytes": "5678"},
                {'t': recent_update_t2, 'disk_usage_bytes': '1234',
                 'bytes_in': '5120', 'bytes_out': '41300', 'num_requests_in': '1120', 'num_requests_out': '7230', 'num_requests_misc': '503',
                 "sum_cpu_seconds": "2334.5", "ram_limit_bytes": "5766"},
                {'t': recent_update_t3, 'disk_usage_bytes': '1234',
                 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513',
                 "sum_cpu_seconds": "4334.5", "ram_limit_bytes": "5987"},
            ]
        }))
        old_update_t1 = datetime.datetime(2021,3,2,3,1,15, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        old_update_t2 = datetime.datetime(2021,3,2,3,1,33, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        old_update_t3 = datetime.datetime(2021,3,2,3,4,5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        domains_config.keys.worker_aggregated_metrics.set(worker_id_deployed_has_action_old_update, json.dumps({
            'lu': "20210302030405",
            'm': [
                {'t': old_update_t1,                                           'num_requests_in': '1000', 'num_requests_out': '7000',                           },
                {'t': old_update_t2, 'bytes_in': '5120', 'bytes_out': '45000',                            'num_requests_out': '6930',                           },
                {'t': old_update_t3, 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513'},
            ]
        }))
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
    assert [o['labels'] for o in updater_metrics.observations] == [
        (worker_id_pending_old_revision1, 'not_deployed_force_update'),
        (worker_id_pending_old_revision2, 'not_deployed_force_update'),
        (worker_id_deployed_no_action, 'force_delete'),
        (worker_id_deployed_has_action_old_update, 'force_update'),
    ]
    force_update_worker_ids = list(domains_config.keys.worker_force_update.iterate_prefix_key_suffixes())
    force_delete_worker_ids = list(domains_config.keys.worker_force_delete.iterate_prefix_key_suffixes())
    assert worker_id_pending_old_revision1 in force_update_worker_ids
    assert worker_id_pending_old_revision2 in force_update_worker_ids
    assert worker_id_deployed_has_action_old_update in force_update_worker_ids
    assert worker_id_deployed_no_action in force_delete_worker_ids
    assert cwm_api_manager.mock_calls_log[0][0] == 'get_cwm_updates'
    assert cwm_api_manager.mock_calls_log[1:] == [
        ('_do_send_agg_metrics', {
            "instanceId": worker_id_deployed_has_action_recent_update,
            "measurements": [
                {"t": recent_update_t1, 'storage_bytes': 1234,
                 "bytes_in": 5000, "bytes_out": 40000, "num_requests_in": 1000, "num_requests_out": 7000, "num_requests_misc": 500,
                 "cpu_seconds": 1234.5, "ram_bytes": 5678},
                {"t": recent_update_t2, 'storage_bytes': 1234,
                 "bytes_in": 5120, "bytes_out": 41300, "num_requests_in": 1120, "num_requests_out": 7230, "num_requests_misc": 503,
                 "cpu_seconds": 2334.5, "ram_bytes": 5766},
                {"t": recent_update_t3, 'storage_bytes': 1234,
                 "bytes_in": 5180, "bytes_out": 42200, "num_requests_in": 1280, "num_requests_out": 7680, "num_requests_misc": 513,
                 "cpu_seconds": 4334.5, "ram_bytes": 5987},
            ]
        }),
        ('_do_send_agg_metrics', {
            'instanceId': worker_id_deployed_has_action_old_update,
            'measurements': [
                {'t': old_update_t1, 'bytes_in': 0, 'bytes_out': 0, 'num_requests_in': 1000, 'num_requests_out': 7000,
                 'num_requests_misc': 0, 'cpu_seconds': 0.0, 'ram_bytes': 0, 'storage_bytes': 0},
                {'t': old_update_t2, 'bytes_in': 5120, 'bytes_out': 45000, 'num_requests_in': 0,  'num_requests_out': 6930,
                 'num_requests_misc': 0, 'cpu_seconds': 0.0, 'ram_bytes': 0, 'storage_bytes': 0},
                {'t': old_update_t3, 'bytes_in': 5180, 'bytes_out': 42200, 'num_requests_in': 1280, 'num_requests_out': 7680,
                 'num_requests_misc': 513, 'cpu_seconds': 0.0, 'ram_bytes': 0, 'storage_bytes': 0},
            ]
        })
    ]
    print("Starting 2nd run_single_iteration")
    cwm_api_manager.mock_calls_log = []
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
    assert len(cwm_api_manager.mock_calls_log) == 1
    assert cwm_api_manager.mock_calls_log[0][0] == 'get_cwm_updates'


def test_cwm_updates(domains_config, deployments_manager, updater_metrics, cwm_api_manager):
    delete_worker_id, delete_hostname, delete_namespace_name = domains_config._set_mock_volume_config('delworker', 'delworker.example.com')
    update_worker_id, update_hostname, update_namespace_name = domains_config._set_mock_volume_config('updworker', 'updworker.example.com')
    deployments_manager.all_releases = [
        {
            "namespace": delete_namespace_name,
            "updated": "1980-03-12 22:11:33",
            "status": "__INVALID__",
            "app_version": "__DOESNT_MATTER__",
            "revision": 99999
        },
        {
            "namespace": update_namespace_name,
            "updated": "1980-03-12 22:11:33",
            "status": "__INVALID__",
            "app_version": "__DOESNT_MATTER__",
            "revision": 99999
        },
    ]
    cwm_api_manager.mock_cwm_updates = [
        {'worker_id': delete_worker_id, 'update_time': datetime.datetime(2021, 8, 10, 10, tzinfo=pytz.UTC)},
        {'worker_id': update_worker_id, 'update_time': datetime.datetime(2021, 9, 10, 10, tzinfo=pytz.UTC)},
    ]
    cwm_api_manager.mock_volume_config_api_calls = {
        'id={}'.format(delete_worker_id): {"errors": [{"code": 12, "info": "Failed to generate instance json", "category": "Object Storage Error"}]},
        'id={}'.format(update_worker_id): {'foo': 'bar'}
    }
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
    assert len(cwm_api_manager.mock_calls_log) == 1
    assert cwm_api_manager.mock_calls_log[0][0] == 'get_cwm_updates'
    expected_from_timestamp = common.now() - datetime.timedelta(seconds=config.UPDATER_DEFAULT_LAST_UPDATE_DATETIME_SECONDS)
    assert (expected_from_timestamp - datetime.timedelta(seconds=2)) < cwm_api_manager.mock_calls_log[0][1] < (expected_from_timestamp + datetime.timedelta(seconds=2))
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.volume_config._(delete_worker_id),
        domains_config.keys.volume_config._(update_worker_id),
    ]) == {
        domains_config.keys.updater_last_cwm_api_update._(): '2021-09-10T10:00:00',
        domains_config.keys.worker_force_update._(update_worker_id): '',
        domains_config.keys.worker_force_delete._(delete_worker_id): '',
        domains_config.keys.worker_force_delete_data._(delete_worker_id): updater.CONFIRM_FORCE_DELETE_DATA,
        domains_config.keys.volume_config._(delete_worker_id): '',
        domains_config.keys.volume_config._(update_worker_id): '',
    }
    # because updater_last_cwm_api_update is set it will not find additional updates
    domains_config.keys.worker_force_update.delete(update_worker_id)
    domains_config.keys.worker_force_delete.delete(delete_worker_id)
    cwm_api_manager.mock_calls_log = []
    cwm_api_manager.mock_cwm_updates = []
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager, cwm_api_manager)
    assert len(cwm_api_manager.mock_calls_log) == 1
    assert cwm_api_manager.mock_calls_log[0][0] == 'get_cwm_updates'
    assert cwm_api_manager.mock_calls_log[0][1] == datetime.datetime(2021, 9, 10, 10, 0, 1, tzinfo=pytz.UTC)
    assert domains_config._get_all_redis_pools_values(blank_keys=[
        domains_config.keys.updater_last_cwm_api_update._(),
        domains_config.keys.volume_config._(delete_worker_id),
        domains_config.keys.volume_config._(update_worker_id),
    ]) == {
        domains_config.keys.updater_last_cwm_api_update._(): '',
        domains_config.keys.worker_force_delete_data._(delete_worker_id): updater.CONFIRM_FORCE_DELETE_DATA,
        domains_config.keys.volume_config._(delete_worker_id): '',
        domains_config.keys.volume_config._(update_worker_id): '',
    }


def test_async(domains_config, deployments_manager, cwm_api_manager):
    updated = (now() - datetime.timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    last_action = now() - datetime.timedelta(minutes=25)
    deployments_manager.all_releases = []
    blank_keys = []
    expected_keys = {}
    for i in range(3):
        worker_id = 'test{}'.format(i)
        namespace_name = 'cwm-worker-{}'.format(worker_id)
        deployments_manager.all_releases.append({
            "namespace": namespace_name,
            "updated": updated,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        })
        domains_config.keys.deployment_last_action.set(namespace_name, last_action.strftime("%Y%m%dT%H%M%S"))
        blank_keys.append(domains_config.keys.deployment_last_action._(namespace_name))
        expected_keys[domains_config.keys.deployment_last_action._(namespace_name)] = ''
        old_update_t1 = datetime.datetime(2021, 3, 2, 3, 1, 15, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        old_update_t2 = datetime.datetime(2021, 3, 2, 3, 1, 33, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        old_update_t3 = datetime.datetime(2021, 3, 2, 3, 4, 5, tzinfo=pytz.UTC).strftime('%Y%m%d%H%M%S')
        domains_config.keys.worker_aggregated_metrics.set(worker_id, json.dumps({'lu': "20210302030405", 'm': [{'t': old_update_t1, 'num_requests_in': '1000', 'num_requests_out': '7000', }, {'t': old_update_t2, 'bytes_in': '5120', 'bytes_out': '45000', 'num_requests_out': '6930', }, {'t': old_update_t3, 'bytes_in': '5180', 'bytes_out': '42200', 'num_requests_in': '1280', 'num_requests_out': '7680', 'num_requests_misc': '513'},]}))
        blank_keys.append(domains_config.keys.worker_aggregated_metrics._(worker_id))
        expected_keys[domains_config.keys.worker_aggregated_metrics._(worker_id)] = ''
        expected_keys[domains_config.keys.worker_force_update._(worker_id)] = ''
        blank_keys.append(domains_config.keys.volume_config._(worker_id))
        expected_keys[domains_config.keys.volume_config._(worker_id)] = ''
    updater.run_single_iteration(domains_config, None, deployments_manager, cwm_api_manager, is_async=True)
    assert domains_config._get_all_redis_pools_values(blank_keys=blank_keys) == expected_keys
