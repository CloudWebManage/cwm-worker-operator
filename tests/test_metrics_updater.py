import datetime

from cwm_worker_operator import metrics_updater

from .mocks.domains_config import MockDomainsConfig
from .mocks.metrics import MockMetricsUpdaterMetrics


def test_update_agg_metrics():
    agg_metrics = {}
    start_time = datetime.datetime(2020, 11, 5, 3, 0)
    for i in range(9999):
        now = start_time + datetime.timedelta(minutes=i)
        metrics_updater.update_agg_metrics(agg_metrics, now, {'now': now})
    assert now == datetime.datetime(2020, 11, 12, 1, 38)
    assert agg_metrics == {
        'lu': '20201112013800',
        'm': {'lu': '20201112013000',
              'v': [{'now': datetime.datetime(2020, 11, 12, 0, 40)},
                    {'now': datetime.datetime(2020, 11, 12, 0, 50)},
                    {'now': datetime.datetime(2020, 11, 12, 1, 0)},
                    {'now': datetime.datetime(2020, 11, 12, 1, 10)},
                    {'now': datetime.datetime(2020, 11, 12, 1, 20)},
                    {'now': datetime.datetime(2020, 11, 12, 1, 30)}]},
        'h': {'lu': '20201112010000',
              'v': [{'now': datetime.datetime(2020, 11, 11, 20, 0)},
                    {'now': datetime.datetime(2020, 11, 11, 21, 0)},
                    {'now': datetime.datetime(2020, 11, 11, 22, 0)},
                    {'now': datetime.datetime(2020, 11, 11, 23, 0)},
                    {'now': datetime.datetime(2020, 11, 12, 0, 0)},
                    {'now': datetime.datetime(2020, 11, 12, 1, 0)}]},
        'd': {'lu': '20201111030000',
              'v': [{'now': datetime.datetime(2020, 11, 6, 3, 0)},
                    {'now': datetime.datetime(2020, 11, 7, 3, 0)},
                    {'now': datetime.datetime(2020, 11, 8, 3, 0)},
                    {'now': datetime.datetime(2020, 11, 9, 3, 0)},
                    {'now': datetime.datetime(2020, 11, 10, 3, 0)},
                    {'now': datetime.datetime(2020, 11, 11, 3, 0)}]}
    }


def test_update_release_metrics():
    namespace_name = "example--001--com"
    domains_config = MockDomainsConfig()
    metrics_updater_metrics = MockMetricsUpdaterMetrics()
    metrics_updater.update_release_metrics(domains_config, metrics_updater_metrics, namespace_name)
    metrics_updater.update_release_metrics(domains_config, metrics_updater_metrics, namespace_name)
    metrics_updater.update_release_metrics(domains_config, metrics_updater_metrics, namespace_name)
    assert len(domains_config.worker_aggregated_metrics_calls) == 3
    domain, agg_metrics = domains_config.worker_aggregated_metrics_calls[0]
    assert domain == 'example.001.com'
    assert set(agg_metrics.keys()) == {'lu', 'd', 'h', 'm'}
    assert isinstance(datetime.datetime.strptime(agg_metrics['lu'], metrics_updater.DATEFORMAT), datetime.datetime)
    assert set(agg_metrics['d'].keys()) == {'lu', 'v'}
    assert set(agg_metrics['h'].keys()) == {'lu', 'v'}
    assert set(agg_metrics['m'].keys()) == {'lu', 'v'}
