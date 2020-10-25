import redis
import datetime
from cwm_worker_operator import domains_config
from contextlib import contextmanager


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


@contextmanager
def get_domains_config_redis_clear():
    dc = domains_config.DomainsConfig()
    r = redis.Redis(connection_pool=dc.redis_pool)
    all_keys = [key.decode() for key in r.keys("*")]
    if len(all_keys) > 0:
        print("Deleting {} keys".format(len(all_keys)))
        r.delete(*all_keys)
    yield dc, r
    r.close()


def test_init():
    with get_domains_config_redis_clear() as (dc, r):
        assert len(r.keys("*")) == 0


def test_worker_keys():
    domain_name = 'example007.com'
    with get_domains_config_redis_clear() as (dc, r):

        ## worker domain waiting for initialization

        r.set("{}:{}".format(domains_config.REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name), "")
        assert dc.get_worker_domains_waiting_for_initlization() == [domain_name]

        ## worker domain initialized (ready for deployment)

        dc.set_worker_ready_for_deployment(domain_name)
        dt = datetime.datetime.strptime(
            r.get("{}:{}".format(domains_config.REDIS_KEY_PREFIX_WORKER_READY_FOR_DEPLOYMENT, domain_name)).decode(),
            "%Y%m%dT%H%M%S.%f")
        assert isinstance(dt, datetime.datetime)
        assert dt == dc.get_worker_ready_for_deployment_start_time(domain_name)
        assert dc.get_worker_domains_ready_for_deployment() == [domain_name]

        ## worker domain waiting for deployment to complete

        dc.set_worker_waiting_for_deployment(domain_name)
        assert dc.get_worker_domains_waiting_for_deployment_complete() == [domain_name]

        ## volume config

        # first call with valid domain - success from api
        metrics = MockMetrics()
        volume_config = dc.get_cwm_api_volume_config(domain_name, metrics)
        assert volume_config['hostname'] == domain_name
        assert volume_config['zone'] == 'EU'
        assert isinstance(datetime.datetime.strptime(volume_config['__last_update'], "%Y%m%dT%H%M%S"), datetime.datetime)
        assert domain_name in metrics.domain_volume_config_success_from_api
        # second call with valid domain - success from cache
        metrics = MockMetrics()
        volume_config = dc.get_cwm_api_volume_config(domain_name, metrics)
        assert volume_config['hostname'] == domain_name
        assert volume_config['zone'] == 'EU'
        assert isinstance(datetime.datetime.strptime(volume_config['__last_update'], "%Y%m%dT%H%M%S"), datetime.datetime)
        assert domain_name in metrics.domain_volume_config_success_from_cache
        # get volume config namespace
        volume_config, namespace = dc.get_volume_config_namespace_from_domain(None, domain_name)
        assert volume_config['hostname'] == domain_name
        assert volume_config['zone'] == 'EU'
        assert namespace == 'example007--com'

        ## worker domain deployment complete - worker ingress hostname is available
        # this also deletes worker keys

        assert len(r.keys("*")) == 4
        dc.set_worker_available(domain_name, 'ingress.hostname')
        assert r.get(domains_config.REDIS_KEY_WORKER_AVAILABLE.format(domain_name)) == b''
        assert r.get(domains_config.REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name)).decode() == 'ingress.hostname'
        assert len(r.keys("*")) == 3

        ## set worker domain errors

        dc.set_worker_error(domain_name, 'test error')
        assert r.get(domains_config.REDIS_KEY_WORKER_ERROR.format(domain_name)).decode() == 'test error'
        assert dc.increment_worker_error_attempt_number(domain_name) == 1
        assert r.get(domains_config.REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name)).decode() == "1"
        assert dc.increment_worker_error_attempt_number(domain_name) == 2
        assert r.get(domains_config.REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name)).decode() == "2"

        ## delete worker keys

        dc.del_worker_keys(None, domain_name)
        assert len(r.keys("*")) == 0


def test_get_volume_config_error():
    domain_name = '__invalid__domain.error'
    with get_domains_config_redis_clear() as (dc, r):
        # first call with invalid domain - error from api
        metrics = MockMetrics()
        volume_config = dc.get_cwm_api_volume_config(domain_name, metrics)
        assert set(volume_config.keys()) == {'__error', '__last_update'}
        assert isinstance(datetime.datetime.strptime(volume_config['__last_update'], "%Y%m%dT%H%M%S"), datetime.datetime)
        assert domain_name in metrics.domain_volume_config_error_from_api
        # second call with invalid domain - error from cache
        metrics = MockMetrics()
        volume_config = dc.get_cwm_api_volume_config(domain_name, metrics)
        assert set(volume_config.keys()) == {'__error', '__last_update'}
        assert isinstance(datetime.datetime.strptime(volume_config['__last_update'], "%Y%m%dT%H%M%S"), datetime.datetime)
        assert domain_name in metrics.domain_volume_config_success_from_cache
        # get volume config namespace
        volume_config, namespace = dc.get_volume_config_namespace_from_domain(None, domain_name)
        assert set(volume_config.keys()) == {'__error', '__last_update'}
        assert namespace == None
