import json
import pytz
import datetime

from cwm_worker_operator import metrics_updater
from cwm_worker_operator import common

from .mocks.metrics import MockMetricsUpdaterMetrics


def iterate_redis_pools(dc):
    for pool in ['ingress', 'internal', 'metrics']:
        with getattr(dc, 'get_{}_redis'.format(pool))() as r:
            yield r


def delete_all_redis_pools_keys(dc):
    for r in iterate_redis_pools(dc):
        for key in r.keys("*"):
            r.delete(key)


def test_update_agg_metrics():
    agg_metrics = {}
    now = datetime.datetime(2020, 11, 5, 3, 0).astimezone(pytz.UTC)
    metrics_updater.update_agg_metrics(agg_metrics, now, {}, limit=2)
    assert agg_metrics == {
        'lu': now.strftime("%Y%m%d%H%M%S"),
        'm': [{'t': now.strftime("%Y%m%d%H%M%S")}]
    }
    for i in range(5):
        now = now + datetime.timedelta(minutes=1)
        metrics_updater.update_agg_metrics(agg_metrics, now, {}, limit=2)
        assert agg_metrics == {
            'lu': now.strftime("%Y%m%d%H%M%S"),
            'm': [{'t': (now - datetime.timedelta(minutes=1)).strftime("%Y%m%d%H%M%S")},
                  {'t': now.strftime("%Y%m%d%H%M%S")}]
        }


def test_update_release_metrics(domains_config, deployments_manager):
    worker_id = 'worker1'
    namespace_name = common.get_namespace_name_from_worker_id(worker_id)
    aggregated_metrics_key = 'worker:aggregated-metrics:{}'.format(worker_id)
    minio_metrics_base_key = 'deploymentid:minio-metrics:{}:'.format(namespace_name)
    metrics_updater_metrics = MockMetricsUpdaterMetrics()
    deployments_manager.prometheus_metrics[namespace_name] = {}
    deployments_manager.kube_metrics[namespace_name] = {
        'ram_limit_bytes': 0,
        'ram_requests_bytes': 0
    }
    now = datetime.datetime(2020, 1, 5, 4, 3, 2).astimezone(pytz.UTC)
    delete_all_redis_pools_keys(domains_config)
    domains_config._set_mock_volume_config(worker_id)

    # no aggregated metrics, no current metrics - aggregated metrics are updated with empty metrics for current minute
    metrics_updater.update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, namespace_name, now=now, update_interval_seconds=59)
    assert json.loads(domains_config.keys.worker_aggregated_metrics.get(worker_id)) == {
        'lu': now.strftime("%Y%m%d%H%M%S"),
        'm': [{'t': now.strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0}]
    }

    # fast forward 61 seconds, another empty current metric is recorded in aggregated metrics
    now = now + datetime.timedelta(seconds=61)
    metrics_updater.update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, namespace_name, now=now, update_interval_seconds=59)
    assert json.loads(domains_config.keys.worker_aggregated_metrics.get(worker_id)) == {
        'lu': now.strftime("%Y%m%d%H%M%S"),
        'm': [{'t': (now-datetime.timedelta(seconds=61)).strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0},
              {'t': now.strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0}]
    }

    # clear all keys and set some current metrics (cpu and ram) - they are added to aggregated metrics
    with domains_config.get_internal_redis() as r:
        [r.delete(key) for key in [aggregated_metrics_key]]
    with domains_config.get_metrics_redis() as r:
        [r.delete(key) for key in r.keys(minio_metrics_base_key + '*')]
        r.set(minio_metrics_base_key+'cpu', '500')
        r.set(minio_metrics_base_key+'ram', '700.5')
    now = now + datetime.timedelta(seconds=61)
    metrics_updater.update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, namespace_name, now=now, update_interval_seconds=59)
    assert json.loads(domains_config.keys.worker_aggregated_metrics.get(worker_id)) == {
        'lu': now.strftime("%Y%m%d%H%M%S"),
        'm': [{'t': now.strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0, 'cpu': 500, 'ram': 700.5}]
    }

    # set different current metrics and fast-forward 61 seconds - they are appended to the aggregated metrics
    # in this case we also set the cpu and ram in different buckets which are also summed as all metrics for each bucket are summed
    # we also add some prometheus metrics this time
    deployments_manager.prometheus_metrics[namespace_name] = {
        'cpu_seconds': '1234',
        'ram_bytes': '5678'
    }
    with domains_config.get_metrics_redis() as r:
        r.set(minio_metrics_base_key + 'cpu', '600')
        r.set(minio_metrics_base_key + 'ram', '800.5')
    now = now + datetime.timedelta(seconds=61)
    metrics_updater.update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, namespace_name, now=now, update_interval_seconds=59)
    assert json.loads(domains_config.keys.worker_aggregated_metrics.get(worker_id)) == {
        'lu': now.strftime("%Y%m%d%H%M%S"),
        'm': [
            {'t': (now-datetime.timedelta(seconds=61)).strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0, 'cpu': 500.0, 'ram': 700.5},
            {
                't': now.strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0, 'cpu': 600.0, 'ram': 800.5,
                'cpu_seconds': '1234', 'ram_bytes': '5678'
            }
        ]
    }

    # fast forward 50 seconds (less than 1 minute), aggregated metrics are not updated
    now = now + datetime.timedelta(seconds=50)
    metrics_updater.update_release_metrics(domains_config, deployments_manager, metrics_updater_metrics, namespace_name, now=now, update_interval_seconds=59)
    assert json.loads(domains_config.keys.worker_aggregated_metrics.get(worker_id)) == {
        'lu': (now - datetime.timedelta(seconds=50)).strftime("%Y%m%d%H%M%S"),
        'm': [
            {'t': (now - datetime.timedelta(seconds=50+61)).strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0, 'cpu': 500.0, 'ram': 700.5},
            {
                't': (now - datetime.timedelta(seconds=50)).strftime("%Y%m%d%H%M%S"), 'disk_usage_bytes': 0, 'ram_limit_bytes': 0, 'ram_requests_bytes': 0, 'cpu': 600.0, 'ram': 800.5,
                'cpu_seconds': '1234', 'ram_bytes': '5678'
            }
        ]
    }
