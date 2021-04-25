import json
import time
import pytz
import datetime
import subprocess
from collections import defaultdict

from cwm_worker_operator import deleter
from cwm_worker_operator import initializer
from cwm_worker_operator import deployer
from cwm_worker_operator import waiter
from cwm_worker_operator import config
from cwm_worker_operator import common

from .mocks.metrics import MockInitializerMetrics, MockDeployerMetrics, MockWaiterMetrics


EXAMPLE007_COM_WORKER_ID = 'worker1'
EXAMPLE007_COM_HOSTNAME = 'example007.com'

MISSING1_WORKER_ID = 'worker2'
MISSING1_HOSTNAME = 'missing.domain1'

MISSING2_WORKER_ID = 'worker3'
MISSING2_HOSTNAME = 'missing.domain2'

INVALIDZONE1_WORKER_ID = 'worker4'
INVALIDZONE1_HOSTNAME = 'invalid.zone1'

INVALIDZONE2_WORKER_ID = 'worker5'
INVALIDZONE2_HOSTNAME = 'invalid.zone2'

FAILTODEPLOY_WORKER_ID = 'worker6'
FAILTODEPLOY_HOSTNAME = 'failtodeploy.domain'

TIMEOUTDEPLOY_WORKER_ID = 'worker7'
TIMEOUTDEPLOY_HOSTNAME = 'timeout.deploy'

WORKERS = {
    EXAMPLE007_COM_WORKER_ID: {
        'hostname': EXAMPLE007_COM_HOSTNAME,
        'volume_config': {
            "id": EXAMPLE007_COM_WORKER_ID, "hostnames": [{'hostname': EXAMPLE007_COM_HOSTNAME}], "zone": "EU"
        },
        'after_initializer': 'ready_for_deployment',
        'after_deployer': 'waiting_for_deployment',
        'after_waiter': 'valid',
    },
    MISSING1_WORKER_ID: {
        'hostname': MISSING1_HOSTNAME,
        'after_initializer': 'error_attempts',
    },
    MISSING2_WORKER_ID: {
        'hostname': MISSING2_HOSTNAME,
        'after_initializer': 'error_attempts',
    },
    INVALIDZONE1_WORKER_ID: {
        "hostname": INVALIDZONE1_HOSTNAME,
        'volume_config': {"id": INVALIDZONE1_WORKER_ID, "hostnames": [{'hostname': INVALIDZONE1_HOSTNAME}], "zone": "US"},
        'after_initializer': 'error',
    },
    INVALIDZONE2_WORKER_ID: {
        "hostname": INVALIDZONE2_HOSTNAME,
        'volume_config': {"id": INVALIDZONE2_WORKER_ID, "hostnames": [{'hostname': INVALIDZONE2_HOSTNAME}], "zone": "IL"},
        'after_initializer': 'error',
    },
    FAILTODEPLOY_WORKER_ID: {
        "hostname": FAILTODEPLOY_HOSTNAME,
        'volume_config': {"id": FAILTODEPLOY_WORKER_ID, "hostnames": [{'hostname': FAILTODEPLOY_HOSTNAME}], "zone": "EU",
                          "minio_extra_configs": {"resources": "---invalid---"}},
        'after_initializer': 'ready_for_deployment',
        'after_deployer': 'error',
    },
    TIMEOUTDEPLOY_WORKER_ID: {
        "hostname": TIMEOUTDEPLOY_HOSTNAME,
        'volume_config': {"id": TIMEOUTDEPLOY_WORKER_ID, "hostnames": [{'hostname': TIMEOUTDEPLOY_HOSTNAME, 'pem': 'invalid', 'key': 'invalid'}], "zone": "EU"},
        'after_initializer': 'ready_for_deployment',
        'after_deployer': 'waiting_for_deployment',
        'after_waiter': 'error'
    },
}


def _assert_after_initializer(worker_id, test_config, dc, attempt_number=1):
    if test_config['after_initializer'] == 'ready_for_deployment':
        assert worker_id in dc.get_worker_ids_ready_for_deployment()
    else:
        assert worker_id not in dc.get_worker_ids_ready_for_deployment()
        if test_config['after_initializer'] == 'error':
            assert dc.keys.hostname_error.get(test_config['hostname']), worker_id
        elif test_config['after_initializer'] == 'error_attempts':
            assert dc.keys.hostname_error_attempt_number.get(test_config['hostname']).decode() == str(attempt_number)
        else:
            raise Exception('unknown after initializer assertion: {}'.format(test_config['after_initializer']))


def _assert_after_deployer(worker_id, test_config, dc):
    if test_config.get('after_deployer') == 'waiting_for_deployment':
        assert worker_id in dc.get_worker_ids_waiting_for_deployment_complete()
    elif test_config.get('after_deployer') == 'error':
        assert dc.keys.hostname_error.get(test_config['hostname'])
    elif test_config.get('after_deployer') is not None:
        raise Exception('unknown after deployer assertion: {}'.format(test_config.get('after_deployer')))


def _assert_after_waiter(worker_id, test_config, dc, debug=False):
    if test_config.get('after_waiter') == 'valid':
        if (
            dc.keys.hostname_available.get(test_config['hostname']) == b''
            and json.loads(dc.keys.hostname_ingress_hostname.get(test_config['hostname']).decode()) == {proto: "nginx.{}.svc.cluster.local".format(common.get_namespace_name_from_worker_id(worker_id)) for proto in ['http', 'https']}
            and test_config['hostname'] not in dc.get_hostnames_waiting_for_initlization()
        ):
            return True
        else:
            if debug:
                print("hostname_available={}".format(dc.keys.hostname_available.get(test_config['hostname'])))
                print("hostname_ingress_hostname={}".format(dc.keys.hostname_ingress_hostname.get(test_config['hostname'])))
                print("hostnames_waiting_for_initlization={}".format(list(dc.get_hostnames_waiting_for_initlization())))
            return False
    elif test_config.get('after_waiter') == 'error':
        if bool(dc.keys.hostname_error.get(test_config['hostname'])):
            return True
        else:
            if debug:
                print("hostname_error={}".format(dc.keys.hostname_error.get(test_config['hostname'])))
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


def _set_volume_configs(dc, worker_id, test_config):
    if test_config.get('volume_config'):
        dc._cwm_api_volume_configs['id:{}'.format(worker_id)] = test_config['volume_config']
        dc._cwm_api_volume_configs['hostname:{}'.format(test_config['hostname'])] = test_config['volume_config']


def _delete_workers(dc):
    print("Deleting workers..")
    for worker_id, test_config in WORKERS.items():
        _set_volume_configs(dc, worker_id, test_config)
        deleter.delete(worker_id, deployment_timeout_string='5m', delete_namespace=True, delete_helm=True,
                       domains_config=dc)
    for worker_id in WORKERS.keys():
        namespace_name = common.get_namespace_name_from_worker_id(worker_id)
        start_time = datetime.datetime.now(pytz.UTC)
        while True:
            returncode, _ = subprocess.getstatusoutput('kubectl get ns {}'.format(namespace_name))
            if returncode == 1:
                break
            if (datetime.datetime.now(pytz.UTC) - start_time).total_seconds() > 30:
                raise Exception("Waiting too long for namespace to be deleted ({})".format(namespace_name))
            time.sleep(1)


def _set_redis_keys(dc):
    print("Setting redis keys..")
    for worker_id, test_config in WORKERS.items():
        dc.keys.hostname_initialize.set(test_config['hostname'], '')
        _set_volume_configs(dc, worker_id, test_config)


def test(domains_config):
    dc = domains_config
    _delete_workers(dc)
    _set_redis_keys(dc)

    print("Running initializer iteration 1")
    mock_initializer_metrics = MockInitializerMetrics()
    initializer.start_daemon(True, with_prometheus=False, initializer_metrics=mock_initializer_metrics, domains_config=dc)
    for worker_id, test_config in WORKERS.items():
        _assert_after_initializer(worker_id, test_config, dc)
    assert _parse_metrics(mock_initializer_metrics) == {
        'error': 2, 'failed_to_get_volume_config': 2, 'invalid_volume_zone': 2, 'initialized': 3, 'success': 5
    }

    print("Running initializer iteration 2")
    initializer.start_daemon(True, with_prometheus=False, initializer_metrics=mock_initializer_metrics, domains_config=dc)
    for worker_id, test_config in WORKERS.items():
        _assert_after_initializer(worker_id, test_config, dc, attempt_number=2)
    assert _parse_metrics(mock_initializer_metrics) == {
        'error': 4, 'failed_to_get_volume_config': 4, 'invalid_volume_zone': 2, 'initialized': 3, 'success': 8}

    print("Running deployer iteration")
    mock_deployer_metrics = MockDeployerMetrics()
    deployer.start_daemon(True, with_prometheus=False, deployer_metrics=mock_deployer_metrics, domains_config=dc,
                          extra_minio_extra_configs={
                              "metricsLogger": {
                                  "withRedis": True,
                                  "REDIS_HOST": "localhost"
                              }
                          })
    for worker_id, test_config in WORKERS.items():
        _assert_after_deployer(worker_id, test_config, dc)
    assert _parse_metrics(mock_deployer_metrics) == {'failed': 1, 'success': 2, 'success_cache': 3}

    print("Running waiter iterations")
    mock_waiter_metrics = MockWaiterMetrics()
    config.WAITER_VERIFY_WORKER_ACCESS = False
    start_time = datetime.datetime.now(pytz.UTC)
    while True:
        waiter.start_daemon(True, with_prometheus=False, waiter_metrics=mock_waiter_metrics, domains_config=dc)
        if all([_assert_after_waiter(worker_id, test_config, dc) for worker_id, test_config in WORKERS.items()]):
            break
        if (datetime.datetime.now(pytz.UTC) - start_time).total_seconds() > 120:
            for worker_id, test_config in WORKERS.items():
                if not _assert_after_waiter(worker_id, test_config, dc, debug=True):
                    print("Failed asserting after waiter for domain: {} test_config: {}".format(worker_id, test_config))
            raise Exception("Waiting too long for workers to be ready")
        time.sleep(5)
    observations = _parse_metrics(mock_waiter_metrics)
    assert set(observations.keys()) == {'success', 'success_cache', 'timeout'}
    assert observations['success'] == 1
    assert observations['timeout'] == 1

    _delete_workers(dc)
