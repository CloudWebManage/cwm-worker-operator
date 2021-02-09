import json
import time
import redis
import subprocess
import datetime
from collections import defaultdict
from contextlib import contextmanager

from cwm_worker_operator import deleter
from cwm_worker_operator import initializer
from cwm_worker_operator import deployer
from cwm_worker_operator import waiter
from cwm_worker_operator import domains_config
from cwm_worker_operator import config

from .mocks.metrics import MockInitializerMetrics, MockDeployerMetrics, MockWaiterMetrics


WORKERS = {
    'example007.com': {
        'after_initializer': 'ready_for_deployment',
        'after_deployer': 'waiting_for_deployment',
        'after_waiter': 'valid',
    },
    'missing1.domain': {
        'after_initializer': 'error_attempts',
    },
    'missing2.domain': {
        'after_initializer': 'error_attempts',
    },
    'invalidzone1.domain': {
        'volume_config': {"hostname": "invalidzone1.domain", "zone": "US"},
        'after_initializer': 'error',
    },
    'invalidzone2.domain': {
        'volume_config': {"hostname": "invalidzone2.domain", "zone": "IL"},
        'after_initializer': 'error',
    },
    'failtodeploy.domain': {
        'volume_config': {"hostname": "failtodeploy.domain", "zone": "EU", "minio_extra_configs": {"httpResources": "---invalid---"}},
        'after_initializer': 'ready_for_deployment',
        'after_deployer': 'error',
    },
    'timeoutdeploy.domain': {
        'volume_config': {"hostname": "timeoutdeploy.domain", "zone": "EU", "certificate_pem": "invalid", "certificate_key": "invalid", "protocol": "https"},
        'after_initializer': 'ready_for_deployment',
        'after_deployer': 'waiting_for_deployment',
        'after_waiter': 'error'
    },
}


@contextmanager
def get_redis(dc):
    r = redis.Redis(connection_pool=dc.redis_pool)
    yield r
    r.close()


def _assert_after_initializer(domain_name, test_config, dc, attempt_number=1):
    if test_config['after_initializer'] == 'ready_for_deployment':
        assert domain_name in dc.get_worker_domains_ready_for_deployment()
    else:
        assert domain_name not in dc.get_worker_domains_ready_for_deployment()
        if test_config['after_initializer'] == 'error':
            with get_redis(dc) as r:
                assert r.get(domains_config.REDIS_KEY_WORKER_ERROR.format(domain_name))
        elif test_config['after_initializer'] == 'error_attempts':
            with get_redis(dc) as r:
                assert r.get(domains_config.REDIS_KEY_WORKER_ERROR_ATTEMPT_NUMBER.format(domain_name)).decode() == str(attempt_number)
        else:
            raise Exception('unknown after initializer assertion: {}'.format(test_config['after_initializer']))


def _assert_after_deployer(domain_name, test_config, dc):
    if test_config.get('after_deployer') == 'waiting_for_deployment':
        assert domain_name in dc.get_worker_domains_waiting_for_deployment_complete()
    elif test_config.get('after_deployer') == 'error':
        with get_redis(dc) as r:
            assert r.get(domains_config.REDIS_KEY_WORKER_ERROR.format(domain_name))
    elif test_config.get('after_deployer') is not None:
        raise Exception('unknown after deployer assertion: {}'.format(test_config.get('after_deployer')))


def _assert_after_waiter(domain_name, test_config, dc, debug=False):
    if test_config.get('after_waiter') == 'valid':
        with get_redis(dc) as r:
            if (
                r.get(domains_config.REDIS_KEY_WORKER_AVAILABLE.format(domain_name)) == b''
                and json.loads(r.get(domains_config.REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name)).decode()) == {proto: "minio-{}.{}.svc.cluster.local".format(proto, domain_name.replace('.', '--')) for proto in ['http', 'https']}
                and domain_name not in dc.get_worker_domains_waiting_for_initlization()
            ):
                return True
            else:
                if debug:
                    print("REDIS_KEY_WORKER_AVAILABLE={}".format(r.get(domains_config.REDIS_KEY_WORKER_AVAILABLE.format(domain_name))))
                    print("REDIS_KEY_WORKER_INGRESS_HOSTNAME={}".format(r.get(domains_config.REDIS_KEY_WORKER_INGRESS_HOSTNAME.format(domain_name))))
                    print("domains_waiting_for_initialization={}".format(list(dc.get_worker_domains_waiting_for_initlization())))
                return False
    elif test_config.get('after_waiter') == 'error':
        with get_redis(dc) as r:
            if bool(r.get(domains_config.REDIS_KEY_WORKER_ERROR.format(domain_name))):
                return True
            else:
                if debug:
                    print("REDIS_KEY_WORKER_ERROR={}".format(r.get(domains_config.REDIS_KEY_WORKER_ERROR.format(domain_name))))
                return False
    elif test_config.get('after_waiter') is not None:
        raise Exception('unkonwn after waiter assertion: {}'.format(test_config.get('after_waiter')))
    else:
        return True


def _parse_metrics(metrics):
    res = defaultdict(int)
    for o in metrics.observations:
        res[o['labels'][1]] += 1
    return dict(res)


def _delete_workers(dc):
    print("Deleting workers..")
    for domain_name in WORKERS.keys():
        deleter.delete(domain_name, deployment_timeout_string='5m', delete_namespace=True, delete_helm=True,
                       domains_config=dc)
    for domain_name in WORKERS.keys():
        namespace_name = domain_name.replace('.', '--')
        start_time = datetime.datetime.now()
        while True:
            returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
            if returncode == 1:
                break
            if (datetime.datetime.now() - start_time).total_seconds() > 30:
                raise Exception("Waiting too long for namespace to be deleted ({})".format(namespace_name))
            time.sleep(1)


def _clear_redis(dc):
    with get_redis(dc) as r:
        all_keys = [key.decode() for key in r.keys("*")]
        if len(all_keys) > 0:
            print("Deleting {} keys".format(len(all_keys)))
            r.delete(*all_keys)


def _set_redis_keys(dc):
    print("Setting redis keys..")
    with get_redis(dc) as r:
        for domain_name, worker_test_config in WORKERS.items():
            r.set('{}:{}'.format(domains_config.REDIS_KEY_PREFIX_WORKER_INITIALIZE, domain_name), '')
            if worker_test_config.get('volume_config'):
                r.set(domains_config.REDIS_KEY_VOLUME_CONFIG.format(domain_name), json.dumps(worker_test_config['volume_config']))


def test():
    dc = domains_config.DomainsConfig()
    _clear_redis(dc)
    _delete_workers(dc)
    _set_redis_keys(dc)

    print("Running initializer iteration 1")
    mock_initializer_metrics = MockInitializerMetrics()
    initializer.start_daemon(True, with_prometheus=False, initializer_metrics=mock_initializer_metrics, domains_config=dc)
    for domain_name, test_config in WORKERS.items():
        _assert_after_initializer(domain_name, test_config, dc)
    assert _parse_metrics(mock_initializer_metrics) == {
        'error': 2, 'failed_to_get_volume_config': 2, 'success_cache': 4, 'invalid_volume_zone': 2, 'initialized': 3, 'success': 1}

    print("Running initializer iteration 2")
    initializer.start_daemon(True, with_prometheus=False, initializer_metrics=mock_initializer_metrics, domains_config=dc)
    for domain_name, test_config in WORKERS.items():
        _assert_after_initializer(domain_name, test_config, dc, attempt_number=2)
    assert _parse_metrics(mock_initializer_metrics) == {
        'error': 2, 'failed_to_get_volume_config': 4, 'success_cache': 6, 'invalid_volume_zone': 2, 'initialized': 3, 'success': 1}

    print("Running deployer iteration")
    mock_deployer_metrics = MockDeployerMetrics()
    deployer.start_daemon(True, with_prometheus=False, deployer_metrics=mock_deployer_metrics, domains_config=dc,
                          extra_minio_extra_configs={
                              "metricsLogger": {
                                  "withRedis": True,
                                  "REDIS_HOST": "localhost"
                              }
                          })
    for domain_name, test_config in WORKERS.items():
        _assert_after_deployer(domain_name, test_config, dc)
    assert _parse_metrics(mock_deployer_metrics) == {'failed': 1, 'success': 2, 'success_cache': 3}

    print("Running waiter iterations")
    mock_waiter_metrics = MockWaiterMetrics()
    config.WAITER_VERIFY_WORKER_ACCESS = False
    start_time = datetime.datetime.now()
    while True:
        waiter.start_daemon(True, with_prometheus=False, waiter_metrics=mock_waiter_metrics, domains_config=dc)
        if all([_assert_after_waiter(domain_name, test_config, dc) for domain_name, test_config in WORKERS.items()]):
            break
        if (datetime.datetime.now() - start_time).total_seconds() > 60:
            for domain_name, test_config in WORKERS.items():
                if not _assert_after_waiter(domain_name, test_config, dc, debug=True):
                    print("Failed asserting after waiter for domain: {} test_config: {}".format(domain_name, test_config))
            raise Exception("Waiting too long for workers to be ready")
        time.sleep(5)
    observations = _parse_metrics(mock_waiter_metrics)
    assert set(observations.keys()) == {'success', 'success_cache', 'timeout'}
    assert observations['success'] == 1
    assert observations['timeout'] == 1

    _delete_workers(dc)
