import json
import pytz
import datetime
from cwm_worker_operator.domains_config import DomainsConfigKey, DomainsConfig
from cwm_worker_operator.common import strptime, get_namespace_name_from_worker_id


class MockMetrics:

    def __init__(self):
        self.domain_volume_config_success_from_api = {}
        self.domain_volume_config_error_from_api = {}
        self.domain_volume_config_success_from_cache = {}

    def cwm_api_volume_config_success_from_api(self, domain_name, start_time):
        self.domain_volume_config_success_from_api[domain_name] = start_time

    def cwm_api_volume_config_error_from_api(self, domain_name, start_time):
        self.domain_volume_config_error_from_api[domain_name] = start_time

    def cwm_api_volume_config_success_from_cache(self, domain_name, start_time):
        self.domain_volume_config_success_from_cache[domain_name] = start_time


def iterate_redis_pools(dc):
    for pool in ['ingress', 'internal', 'metrics']:
        with getattr(dc, 'get_{}_redis'.format(pool))() as r:
            yield r


def get_all_redis_pools_keys(dc):
    all_keys = []
    for r in iterate_redis_pools(dc):
        for key in r.keys("*"):
            all_keys.append(key.decode())
    return all_keys


def test_init(domains_config):
    dc = domains_config
    for r in iterate_redis_pools(dc):
        assert len(r.keys("*")) == 0


def test_worker_keys(domains_config):
    dc = domains_config
    hostname = 'example007.com'
    worker_id = 'worker1'

    ## worker domain waiting for initialization

    dc.keys.hostname_initialize.set(hostname, '')
    assert dc.get_hostnames_waiting_for_initlization() == [hostname]

    ## worker domain initialized (ready for deployment)

    dc.set_worker_ready_for_deployment(worker_id)
    dt = strptime(dc.keys.worker_ready_for_deployment.get(worker_id).decode(), "%Y%m%dT%H%M%S.%f")
    assert isinstance(dt, datetime.datetime)
    assert dt == dc.get_worker_ready_for_deployment_start_time(worker_id)
    assert dc.get_worker_ids_ready_for_deployment() == [worker_id]

    ## worker domain waiting for deployment to complete

    dc.set_worker_waiting_for_deployment(worker_id)
    assert dc.get_worker_ids_waiting_for_deployment_complete() == [worker_id]

    ## volume config

    # first call with valid domain - success from api
    metrics = MockMetrics()
    dc._cwm_api_volume_configs['id:{}'.format(worker_id)] = {'instanceId': worker_id, 'hostname': hostname, 'zone': 'EU'}
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname]
    assert volume_config.zone == 'EU'
    assert isinstance(strptime(volume_config._last_update, "%Y%m%dT%H%M%S"), datetime.datetime)
    assert worker_id in metrics.domain_volume_config_success_from_api
    # second call with valid domain - success from cache
    metrics = MockMetrics()
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname]
    assert volume_config.zone == 'EU'
    assert isinstance(strptime(volume_config._last_update, "%Y%m%dT%H%M%S"), datetime.datetime)
    assert worker_id in metrics.domain_volume_config_success_from_cache
    # get volume config namespace
    volume_config, namespace = dc.get_volume_config_namespace_from_worker_id(None, worker_id)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname]
    assert volume_config.zone == 'EU'
    assert namespace == get_namespace_name_from_worker_id(worker_id)

    ## worker domain deployment complete - worker ingress hostname is available
    # this also deletes worker keys

    assert len(get_all_redis_pools_keys(dc)) == 4
    dc.set_worker_available(worker_id, {'http':'ingress-http.hostname', 'https': 'ingress-https.hostname'})
    assert dc.keys.hostname_available.get(hostname) == b''
    assert json.loads(
        dc.keys.hostname_ingress_hostname.get(hostname).decode()
    ) == {
        'http':'ingress-http.hostname', 'https': 'ingress-https.hostname'
    }
    assert len(get_all_redis_pools_keys(dc)) == 3

    ## set worker domain errors

    dc.set_worker_error(worker_id, 'test error')
    assert dc.keys.hostname_error.get(hostname).decode() == 'test error'
    assert dc.increment_worker_error_attempt_number(hostname) == 1
    assert dc.keys.hostname_error_attempt_number.get(hostname).decode() == "1"
    assert dc.increment_worker_error_attempt_number(hostname) == 2
    assert dc.keys.hostname_error_attempt_number.get(hostname).decode() == "2"

    ## delete worker keys

    dc.del_worker_keys(worker_id)
    assert len(get_all_redis_pools_keys(dc)) == 0


def test_get_volume_config_error(domains_config):
    dc = domains_config
    worker_id = 'worker1'
    # first call with invalid domain - error from api
    metrics = MockMetrics()
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config._error
    assert isinstance(strptime(volume_config._last_update, "%Y%m%dT%H%M%S"), datetime.datetime)
    assert worker_id in metrics.domain_volume_config_error_from_api
    # second call with invalid domain - error from cache
    metrics = MockMetrics()
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config._error
    assert isinstance(strptime(volume_config._last_update, "%Y%m%dT%H%M%S"), datetime.datetime)
    assert worker_id in metrics.domain_volume_config_success_from_cache
    # get volume config namespace
    volume_config, namespace = dc.get_volume_config_namespace_from_worker_id(None, worker_id)
    assert volume_config._error
    assert volume_config._last_update
    assert namespace == None


def test_volume_config_force_update(domains_config):
    dc = domains_config
    worker_id = 'worker1'
    hostname = 'example007.com'
    metrics = MockMetrics()
    # set volume config in redis
    dc.keys.volume_config.set(worker_id, json.dumps({'instanceId': worker_id, 'hostname': hostname, "zone": "FOOBAR"}))
    # without force update, this volume config is returned
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname]
    assert volume_config.zone == 'FOOBAR'
    # with force update, we get an error as worker_id does not exist
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics, force_update=True)
    assert volume_config._error
    assert volume_config._last_update


def test_worker_forced_delete_update(domains_config):
    dc = domains_config
    update_worker_id_1 = 'update1'
    update_worker_id_2 = 'update2'
    delete_worker_id_1 = 'delete1'
    delete_worker_id_2 = 'delete2'
    dc.set_worker_force_update(update_worker_id_1)
    dc.set_worker_force_update(update_worker_id_2)
    dc.set_worker_force_delete(delete_worker_id_1)
    dc.set_worker_force_delete(delete_worker_id_2)
    convdeletedomain = lambda d: "worker_id: {}, allow_cancel: {}".format(d['worker_id'], d['allow_cancel'])
    assert {convdeletedomain(d) for d in dc.iterate_domains_to_delete()} == {
        convdeletedomain({'worker_id': delete_worker_id_1, 'allow_cancel': False}),
        convdeletedomain({'worker_id': delete_worker_id_2, 'allow_cancel': False})
    }
    dc.set_worker_force_delete(delete_worker_id_2, allow_cancel=True)
    assert {convdeletedomain(d) for d in dc.iterate_domains_to_delete()} == {
        convdeletedomain({'worker_id': delete_worker_id_1, 'allow_cancel': False}),
        convdeletedomain({'worker_id': delete_worker_id_2, 'allow_cancel': True})
    }
    assert set(dc.get_worker_ids_force_update()) == {update_worker_id_1, update_worker_id_2}
    assert dc.keys.worker_force_update.exists(update_worker_id_2)
    assert dc.keys.worker_force_delete.exists(delete_worker_id_2)
    dc.del_worker_keys(update_worker_id_2)
    dc.del_worker_keys(delete_worker_id_2)
    assert not dc.keys.worker_force_update.exists(update_worker_id_2)
    assert not dc.keys.worker_force_delete.exists(delete_worker_id_2)


def test_worker_aggregated_metrics(domains_config):
    dc = domains_config
    domain_name = 'example007.com'
    agg_metrics = {'this is': 'metrics'}
    dc.set_worker_aggregated_metrics(domain_name, agg_metrics)
    assert dc.get_worker_aggregated_metrics(domain_name, clear=True) == agg_metrics
    assert dc.get_worker_aggregated_metrics(domain_name) == None


def test_deployment_api_metrics(domains_config):
    dc = domains_config
    namespace_name = 'worker1'
    assert dc.get_deployment_api_metrics(namespace_name) == {}
    dc.keys.deployment_api_metric.set(namespace_name + ':mymetric', '5')
    assert dc.get_deployment_api_metrics(namespace_name) == {'mymetric': '5'}


def test_deployment_last_action(domains_config):
    dc = domains_config
    namespace_name = 'worker1'
    assert dc.get_deployment_last_action(namespace_name) == None
    dc.keys.deployment_last_action.set(namespace_name, '20201103T221112.123456')
    assert dc.get_deployment_last_action(namespace_name) == datetime.datetime(2020, 11, 3, 22, 11, 12, tzinfo=pytz.UTC)
    dc.keys.deployment_last_action.set(namespace_name, '2020-11-03T22:11:12.123456')
    assert dc.get_deployment_last_action(namespace_name) == datetime.datetime(2020, 11, 3, 22, 11, 12, tzinfo=pytz.UTC)


def test_get_worker_ready_for_deployment_start_time_exception(domains_config):
    dc = domains_config
    worker_id = 'worker1'
    dc.keys.worker_ready_for_deployment.set(worker_id, 'foobar')
    dt = dc.get_worker_ready_for_deployment_start_time(worker_id)
    assert isinstance(dt, datetime.datetime)
    assert (datetime.datetime.now(pytz.UTC) - dt).total_seconds() < 5


def test_del_worker_keys(domains_config):
    worker_id = 'worker1'
    namespace_name = get_namespace_name_from_worker_id(worker_id)
    hostname = 'example007.com'
    for key_name in dir(domains_config.keys):
        key = getattr(domains_config.keys, key_name)
        keys_summary_param = getattr(key, 'keys_summary_param', None)
        if not isinstance(key, DomainsConfigKey) or key_name == 'alerts' or keys_summary_param == 'node':
            continue
        if key_name == 'deployment_api_metric':
            key.set('{}:foo'.format(namespace_name), '')
        elif key_name == 'volume_config':
            key.set(worker_id, json.dumps({'instanceId': worker_id, 'hostname': hostname}))
        elif keys_summary_param == 'hostname':
            key.set(hostname, '')
        elif keys_summary_param == 'worker_id':
            key.set(worker_id, '')
        elif keys_summary_param == 'namespace_name':
            key.set(namespace_name, '')
        else:
            raise Exception("Invalid keys_summary_param: {}".format(keys_summary_param))
    domains_config.del_worker_keys(worker_id)
    assert domains_config._get_all_redis_pools_keys() == {
        'deploymentid:last_action:worker1',
        'deploymentid:minio-metrics:worker1:foo',
        'worker:aggregated-metrics-last-sent-update:worker1',
        'worker:aggregated-metrics:worker1',
        'worker:total-used-bytes:worker1',
    }
    domains_config.del_worker_keys(worker_id, with_metrics=True)
    assert domains_config._get_all_redis_pools_keys() == set()


def test_redis_pools(domains_config):
    dc = domains_config
    with dc.get_internal_redis() as internal_redis:
        with dc.get_metrics_redis() as metrics_redis:
            with dc.get_ingress_redis() as ingress_redis:
                internal_redis.set('foo', 'bar')
                assert internal_redis.exists('foo') and not metrics_redis.exists('foo') and not ingress_redis.exists('foo')


def test_get_volume_config_api_call():
    domains_config = DomainsConfig()
    worker_id = '4ee4ab056c'
    res = domains_config._cwm_api_volume_config_api_call('id', worker_id)
    assert res['type'] == 'instance'
    assert res['instanceId'] == worker_id
    assert res['hostname'] == '{}.eu.cloudwm-obj.com'.format(worker_id)
    assert res['zone'] == 'EU'
    assert len(res['client_id']) > 10
    assert len(res['secret']) > 10
    assert isinstance(res['certificate_key'], list)
    assert isinstance(res['certificate_pem'], list)
    assert res['cache'] is True
    assert res['cache-expiry'] == 60
    assert res['cache-exclude'] == ''
    assert res['minio-browser'] is True
    mec = res['minio_extra_configs']
    assert isinstance(mec['hostnames'], list)
