import datetime

from cwm_worker_operator import updater
from cwm_worker_operator import config


def test_updater_daemon(domains_config, deployments_manager, updater_metrics):
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
    domains_config.deployment_last_action["deployed--no--action"] = ''
    domains_config.deployment_last_action["deployed--has--action--recent-update"] = datetime.datetime.now() - datetime.timedelta(minutes=25)
    domains_config.deployment_last_action["deployed--has--action--old-update"] = datetime.datetime.now() - datetime.timedelta(minutes=25)
    domains_config.deployment_last_action["deployed--no--action--recent-update"] = ''
    updater.run_single_iteration(domains_config, updater_metrics, deployments_manager)
    assert [o['labels'] for o in updater_metrics.observations] == [
        ('pending.old.revision1', 'not_deployed_force_update'),
        ('pending.old.revision2', 'not_deployed_force_update'),
        ('deployed.no.action', 'force_delete'),
        ('deployed.has.action.old-update', 'force_update'),
    ]
    assert domains_config.domain_worker_force_update_calls == {
        "pending.old.revision1": [True],
        "pending.old.revision2": [True],
        "deployed.has.action.old-update": [True],
    }
    assert domains_config.domain_worker_force_delete_calls == {
        "deployed.no.action": [True],
    }
