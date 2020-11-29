import datetime

from cwm_worker_operator import metrics_updater

from .mocks.domains_config import MockDomainsConfig
from .mocks.metrics import MockMetricsUpdaterMetrics


def test_update_agg_metrics():
    agg_metrics = {}
    start_time = datetime.datetime(2020, 11, 5, 3, 0)
    for i in range(3):
        now = start_time + datetime.timedelta(minutes=i)
        metrics_updater.update_agg_metrics(agg_metrics, now, {'now': now})
    assert now == datetime.datetime(2020, 11, 5, 3, 2)
    assert agg_metrics == {
        'lu': '20201105030200',
        'm': [{'now': datetime.datetime(2020, 11, 5, 3, 0)},
              {'now': datetime.datetime(2020, 11, 5, 3, 1)},
              {'now': datetime.datetime(2020, 11, 5, 3, 2)}]
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
    assert set(agg_metrics.keys()) == {'lu', 'm'}
    assert isinstance(datetime.datetime.strptime(agg_metrics['lu'], metrics_updater.DATEFORMAT), datetime.datetime)
    assert len(agg_metrics['m']) == 1
