import os
import json
import datetime

import pytz

from cwm_worker_operator.domains_config import DomainsConfigKey, DomainsConfig, VolumeConfigGatewayTypeS3, DomainsConfigKeyPrefixInt
from cwm_worker_operator.common import strptime, get_namespace_name_from_worker_id
from cwm_worker_operator import config

from .common import set_volume_config_key, get_volume_config_dict, get_volume_config_json


CERTIFICATE_PEM = ["-----BEGIN CERTIFICATE-----", "MIIETTCCAzWgAwIBAgIBADANBgkqhkiG9w0BAQsFADCBwDEnMCUGA1UEAwweNGVl", "NGFiMDU2Yy5nZW8uY2xvdWR3bS1vYmouY29tMSkwJwYJKoZIhvcNAQkBFhpvYmpl", "Y3RzdG9yYWdlb3JpQGdtYWlsLmNvbTEiMCAGA1UECgwZb2JqZWN0c3RvcmFnZS5j", "bG91ZHdtLmNvbTEiMCAGA1UECwwZb2JqZWN0c3RvcmFnZS5jbG91ZHdtLmNvbTEL", "MAkGA1UEBhMCWFgxFTATBgNVBAcMDERlZmF1bHQgQ2l0eTAeFw0yMTA1MTAxMjM3", "MDdaFw0yMjA1MTAxMjM3MDdaMIHAMScwJQYDVQQDDB40ZWU0YWIwNTZjLmdlby5j", "bG91ZHdtLW9iai5jb20xKTAnBgkqhkiG9w0BCQEWGm9iamVjdHN0b3JhZ2VvcmlA", "Z21haWwuY29tMSIwIAYDVQQKDBlvYmplY3RzdG9yYWdlLmNsb3Vkd20uY29tMSIw", "IAYDVQQLDBlvYmplY3RzdG9yYWdlLmNsb3Vkd20uY29tMQswCQYDVQQGEwJYWDEV", "MBMGA1UEBwwMRGVmYXVsdCBDaXR5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB", "CgKCAQEAuV7j9Vla8Zr59lBrTIcQlLtDjwL+/hXjPNz0nOKqt2YmjDuZ+c5+A0k/", "BcMpkh8byttFfKhkz66HefO6BzI+at11PyRn/zfQ6NpRAUMIwJb9wuIcNH5e5RtC", "0D3ZZoQVtHz0+UyCQdCgQ5/n7AQ9g0j1u1dNU/1qJ5y37vh8TFiVxuiQ/A2lLJQq", "Hccd6z39jC9HzXrVrH7TowHy4tgGieg1F41rqLuW7vl4vScnb6efZpi1a/5iMy8f", "RVLiSlpTWcGc7Ood1LoxzviR5HENZ8+ILYkbdBUJ6ZgnP4g+woY8Jo5WoeT8ruwr", "YSNpbz7QFahVw1s7Ypr7z5EHB9PTdQIDAQABo1AwTjAdBgNVHQ4EFgQUFexsmCL7", "uySB9HnU4TUx7Qn5gugwHwYDVR0jBBgwFoAUFexsmCL7uySB9HnU4TUx7Qn5gugw", "DAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEARQMUrM1zANELXKDWRc2T", "TWQvj/0LmkhLnxeI4B66l1unFMwJNi5Rvokz+CsA7rwEOwHeCPcUGcQNbQl5/KFf", "E8k8jtlpatS/dN6ZlRFGVQV5AOcL1aKVMfsjgSjwGJCDgJ2/A0KWL/fQ7O5+0+Fh", "s9Gq8YWgFLBzsS/j1JxdA4z9jfSj8maMQNx0RZClfCYXyWqw0fgDu1U/GT28XTT6", "LLwK/1bkPQygIrnYN3A1vNAR+8oGZqf00MMaY7w/Of61mMm9HK03wHu9OI3B9Luh", "SsUwkNFMcGFzf9qkf8+6Pu1f6rMR9oDHWAq3ipKunNqJpHPlEzBkrf9OeoUPkxZ7", "nw==", "-----END CERTIFICATE-----"]
CERTIFICATE_KEY = ["-----BEGIN PRIVATE KEY-----", "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC5XuP1WVrxmvn2", "UGtMhxCUu0OPAv7+FeM83PSc4qq3ZiaMO5n5zn4DST8FwymSHxvK20V8qGTProd5", "87oHMj5q3XU/JGf/N9Do2lEBQwjAlv3C4hw0fl7lG0LQPdlmhBW0fPT5TIJB0KBD", "n+fsBD2DSPW7V01T/WonnLfu+HxMWJXG6JD8DaUslCodxx3rPf2ML0fNetWsftOj", "AfLi2AaJ6DUXjWuou5bu+Xi9Jydvp59mmLVr/mIzLx9FUuJKWlNZwZzs6h3UujHO", "+JHkcQ1nz4gtiRt0FQnpmCc/iD7Chjwmjlah5Pyu7CthI2lvPtAVqFXDWztimvvP", "kQcH09N1AgMBAAECggEAAfFztEu2f1ffjOx04316+AQqhiJC6Aj0s9uhGM/reDay", "6r9pMswuV/x5k6bjFawLz4mS5eah/+dVdjrO1Wp6awZdR0cra+p63yYCuV+phNNQ", "X62dHBPDDOXHQoWTdNann5e7va1GpEf6lhrkBH5a4rhuEwOsRNggN8AV0YR7URWM", "Exz+nC3Krczm+nLf7AsAOgKib7R7aEPkds8FEfxrmeirmSx3Vi54stH+lx5qHY04", "Dl5/xDsXwAU09orvar68lRfBEmncfilUk7puYa0gK1n1t6uZlnDNncPG/GRFtuMp", "3BF0HOpa3qARE0ZfJGvFK0MsdGKi7SrG2+JgjlG/9QKBgQDceUGsbLY8TZVChrxS", "lzdMGCVFElGefI5vaA3AYxoUFLIX/3s1tPqJkcbAaT+Xh2++pMUig6uaW5uQb+FX", "ewnSPf51CUqLxMWd0uQN2idCsNhFP0pDUFYAhutMtHlO0zRyIDw8g06H7bPou8nJ", "9KkGhDgtplHqmfVkYZziRMLjpwKBgQDXPZpTilj0BArpUog75QJ+Ze5E7vzUiIOu", "3lw1GvKkdF1shfltO759C7Sd1BbMqL7q+MT9lOfXc1qNEFuSYbPgMZ9STpgnG5Ks", "LyDFlXbwLEwyTMbCgv68aTxpMwU1jtpEiP+uqcdZ7rR1kc55jCGtm76D8iZD0JUv", "lzpoUmqjgwKBgAClWkvnBaGnmIhZXLPhPYg7ieBp7VNJiiFJbMDjiXAFn3/yf6no", "ndNJWgu2QzlubCVi1jEDsb0CB7KkoURgV+cFx3kQTeea6/lKZOClgvfvDLMnPFB2", "K8pUmtveq3xPohezgHms6M39JEnKQw0UampaeM+pbRQC33Ur1AnVqbyBAoGAfGyb", "EuHt7BmOKTTRljYbi+/mnii9NSs5XFQkX3qVe6Xc/8gu2QtpYaXrojUhfOuree+X", "CLQUlcKUPOmQ1fzu25Iz9IOEh070Kd8QhceSOuKQpZ8mYvkQwt/e0T1yLHTJDkdX", "7qMsn3tTDIfeIPt12IMozeOkZR1lsF4uoHHMPXsCgYB8R8dmpClH7EtM9YGhcLG7", "/VsQwQDphUIZbXk96IuniM4zaaJNsOwnOnKLSCbF+xVIx9/rXdAQkQz41/aVRpbV", "wxzh66N26SXnC1xg0eBb8m+52dZ6cXXKClLTyYTlQANeXhRgI3VNduZrY+riNC+v", "V2r1dtutQ5v0tQm1MIGvxw==", "-----END PRIVATE KEY-----"]
INTERMEDIATE_CERTIFICATES = ["-----BEGIN CERTIFICATE-----", "MIIETTCCAzINTERMEDIATE_CERTIFICATE_1", "nw==", "-----END CERTIFICATE-----", "-----BEGIN CERTIFICATE-----", "MIIETTCCAzINTERMEDIATE_CERTIFICATE_2", "nw==", "-----END CERTIFICATE-----"]

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
    dc._cwm_api_volume_configs['id:{}'.format(worker_id)] = get_volume_config_dict(
        worker_id=worker_id, hostname=hostname,
        with_ssl={
            'certificate_key': CERTIFICATE_KEY,
            'certificate_pem': CERTIFICATE_PEM
        },
        additional_hostnames=[
            {'hostname': hostname + '2', 'certificate_key': CERTIFICATE_KEY, 'certificate_pem': CERTIFICATE_PEM},
            {'hostname': hostname + '3', 'certificate_key': CERTIFICATE_KEY, 'certificate_pem': CERTIFICATE_PEM},
        ],
        additional_volume_config={
            'zone': 'EU'
        }
    )
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname, hostname + '2', hostname + '3']
    assert volume_config.zone == 'EU'
    assert isinstance(strptime(volume_config._last_update, "%Y%m%dT%H%M%S"), datetime.datetime)
    assert worker_id in metrics.domain_volume_config_success_from_api
    # second call with valid domain - success from cache
    metrics = MockMetrics()
    volume_config = dc.get_cwm_api_volume_config(worker_id=worker_id, metrics=metrics)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname, hostname + '2', hostname + '3']
    assert volume_config.zone == 'EU'
    assert isinstance(strptime(volume_config._last_update, "%Y%m%dT%H%M%S"), datetime.datetime)
    assert worker_id in metrics.domain_volume_config_success_from_cache
    # get volume config namespace
    volume_config, namespace = dc.get_volume_config_namespace_from_worker_id(None, worker_id)
    assert volume_config.id == worker_id
    assert volume_config.hostnames == [hostname, hostname + '2', hostname + '3']
    assert volume_config.zone == 'EU'
    assert volume_config.hostname_certs == {
        hostname: {'privkey': "\n".join(CERTIFICATE_KEY), 'fullchain': "\n".join(CERTIFICATE_PEM), 'chain': ''},
        hostname + '2': {'privkey': "\n".join(CERTIFICATE_KEY), 'fullchain': "\n".join(CERTIFICATE_PEM), 'chain': ''},
        hostname + '3': {'privkey': "\n".join(CERTIFICATE_KEY), 'fullchain': "\n".join(CERTIFICATE_PEM), 'chain': ''},
    }
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
    assert len(get_all_redis_pools_keys(dc)) == 7

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


def test_volume_config_hostname_worker_id_cache(domains_config):
    dc = domains_config
    worker_id = 'worker1'
    hostname = 'example007.com'
    dc._cwm_api_volume_configs['hostname:{}'.format(hostname)] = {
        'instanceId': worker_id, 'minio_extra_configs': {'hostnames': [{'hostname': hostname}]}
    }
    volume_config = dc.get_cwm_api_volume_config(hostname=hostname)
    assert volume_config.id == worker_id

    # empty volume configs and try to get it from cache
    dc._cwm_api_volume_configs['hostname:{}'.format(hostname)] = {}
    volume_config = dc.get_cwm_api_volume_config(hostname=hostname)
    assert volume_config.id == worker_id
    assert volume_config.hostnames[0] == hostname


def test_volume_config_force_update(domains_config):
    dc = domains_config
    worker_id = 'worker1'
    hostname = 'example007.com'
    metrics = MockMetrics()
    # set volume config in redis
    set_volume_config_key(dc, worker_id=worker_id, hostname=hostname, additional_volume_config={"zone": "FOOBAR"})
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
    dc.keys.deployment_last_action.set(namespace_name, '2020-11-03T22:11:12+00:00')
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
        if not isinstance(key, DomainsConfigKey) or key_name in ['alerts', 'updater_last_cwm_api_update'] or keys_summary_param == 'node':
            continue
        val = '1' if isinstance(key, DomainsConfigKeyPrefixInt) else ''
        if key_name == 'deployment_api_metric':
            key.set('{}:foo'.format(namespace_name), val)
        elif key_name == 'volume_config':
            key.set(worker_id, get_volume_config_json(worker_id=worker_id, hostname=hostname))
        elif keys_summary_param == 'hostname':
            key.set(hostname, val)
        elif keys_summary_param == 'worker_id':
            key.set(worker_id, val)
        elif keys_summary_param == 'namespace_name':
            key.set(namespace_name, val)
        else:
            raise Exception("Invalid keys_summary_param: {}".format(keys_summary_param))
    domains_config.del_worker_keys(worker_id)
    assert domains_config._get_all_redis_pools_keys() == {
        'deploymentid:last_action:{}'.format(namespace_name),
        'deploymentid:minio-metrics:{}:foo'.format(namespace_name),
        'worker:aggregated-metrics-last-sent-update:worker1',
        'worker:aggregated-metrics:worker1',
        'worker:total-used-bytes:worker1'
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
    worker_id = os.environ['TEST_WORKER_ID']
    res = domains_config._cwm_api_volume_config_api_call('id', worker_id)
    assert res['type'] == 'instance'
    assert res['instanceId'] == worker_id
    assert res['zone'] == 'EU'
    assert len(res['client_id']) > 10
    assert len(res['secret']) > 10
    assert res['cache'] is True
    assert res['cache-expiry'] == 60
    assert res['cache-exclude'] == ''
    assert res['minio-browser'] is True
    mec = res['minio_extra_configs']
    assert isinstance(mec['hostnames'], list)
    mech = mec['hostnames'][0]
    assert mech['hostname'] == '{}.as.cloudwm-obj.com'.format(worker_id)
    assert set(mec['protocols-enabled']) == {'HTTP', 'HTTPS'}


def test_get_volume_config_api_call_gateway():
    domains_config = DomainsConfig()
    worker_id = os.environ['TEST_GATEWAY_WORKER_ID']
    res = domains_config._cwm_api_volume_config_api_call('id', worker_id)
    # print(res)
    assert res['type'] == 'gateway'
    assert res['instanceId'] == worker_id
    assert res['provider'] == 'cwm'
    assert len(res['client_id']) > 10
    assert len(res['secret']) > 10
    assert len(res['credentials']['instanceId']) > 5
    assert len(res['credentials']['clientId']) > 10
    assert len(res['credentials']['secret']) > 10
    assert res['cache'] is True
    assert res['cache-expiry'] == 60
    assert res['cache-exclude'] == ''
    assert res['minio-browser'] is True
    mec = res['minio_extra_configs']
    assert isinstance(mec['hostnames'], list)
    got_hostname = False
    for mech in mec['hostnames']:
        if mech['hostname'] == '{}.eu.cloudwm-obj.com'.format(worker_id):
            assert isinstance(mech['privateKey'], list)
            assert isinstance(mech['chain'], list) or not mech['chain']
            assert isinstance(mech['fullChain'], list)
            got_hostname = True
    assert got_hostname


def test_volume_config_gateway(domains_config):
    worker_id, hostname = 'worker1', 'worker1.com'
    gateway_worker_id, gateway_hostname = 'worker2', 'worker2.com'

    # first request - set values in mock api, they will be saved in redis cache
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = get_volume_config_dict(
        worker_id=worker_id, hostname=hostname, with_ssl=True, additional_volume_config={
            'type': 'gateway',
            'provider': 'cwm',
            'credentials': {
                'instanceId': 'worker2',
                'clientId': 'accesskey',
                'secret': 'secret'
            }
        }
    )
    domains_config._cwm_api_volume_configs['id:{}'.format(gateway_worker_id)] = get_volume_config_dict(
        worker_id=gateway_worker_id, hostname=gateway_hostname, with_ssl=True
    )
    volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
    assert volume_config.id == worker_id
    assert isinstance(volume_config.gateway, VolumeConfigGatewayTypeS3)
    assert volume_config.gateway.url == 'https://worker2.com'
    assert volume_config.gateway.access_key == 'accesskey'
    assert volume_config.gateway.secret_access_key == 'secret'

    # second request - delete the values in mock api, but cached values will be returned from redis cache
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = {}
    domains_config._cwm_api_volume_configs['id:{}'.format(gateway_worker_id)] = {}
    volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
    assert isinstance(volume_config.gateway, VolumeConfigGatewayTypeS3)
    assert volume_config.gateway.url == 'https://worker2.com'

    # third request - change values in mock api (disable minio-browser) and force update, so values will be returned from api
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = get_volume_config_dict(
        worker_id=worker_id, hostname=hostname, with_ssl=True, additional_volume_config={
            'type': 'gateway',
            'provider': 'cwm',
            'credentials': {
                'instanceId': 'worker2',
                'clientId': 'accesskey',
                'secret': 'secret'
            },
            'minio-browser': False
        }
    )
    domains_config._cwm_api_volume_configs['id:{}'.format(gateway_worker_id)] = get_volume_config_dict(
        worker_id=gateway_worker_id, hostname=gateway_hostname + '.modified', with_ssl=True
    )
    volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id, force_update=True)
    assert volume_config.browser_enabled is False
    assert isinstance(volume_config.gateway, VolumeConfigGatewayTypeS3)
    assert volume_config.gateway.url == 'https://worker2.com.modified'


def test_get_volume_config_api_call_gateway_aws():
    domains_config = DomainsConfig()
    worker_id = os.environ['TEST_GATEWAY_AWS_WORKER_ID']
    res = domains_config._cwm_api_volume_config_api_call('id', worker_id)
    assert res['instanceId'] == worker_id
    assert res['type'] == 'gateway'
    assert res['provider'] == 'aws'
    assert len(res['credentials']['accessKey']) > 5
    assert len(res['credentials']['secretKey']) > 5


def test_get_volume_config_api_call_gateway_azure():
    domains_config = DomainsConfig()
    worker_id = os.environ['TEST_GATEWAY_AZURE_WORKER_ID']
    res = domains_config._cwm_api_volume_config_api_call('id', worker_id)
    assert res['instanceId'] == worker_id
    assert res['type'] == 'gateway'
    assert res['provider'] == 'azure'
    assert len(res['credentials']['accountName']) > 3
    assert len(res['credentials']['accountKey']) > 5


def test_get_volume_config_api_call_gateway_google():
    domains_config = DomainsConfig()
    worker_id = os.environ['TEST_GATEWAY_GOOGLE_WORKER_ID']
    res = domains_config._cwm_api_volume_config_api_call('id', worker_id)
    print(res)
    assert res['instanceId'] == worker_id
    assert res['type'] == 'gateway'
    assert res['provider'] == 'gcs'
    assert isinstance(res['credentials']['credentialsJson'], dict)
    assert len(res['credentials']['projectId']) > 3


def test_get_volume_config_cache_attributes(domains_config):
    worker_id, hostname = 'worker1', 'worker1.com'
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = get_volume_config_dict(
        worker_id=worker_id, hostname=hostname, with_ssl=True, additional_volume_config={
            'cache': True,
            'cache-exclude': 'jpg|pdf|txt',
            'cache-expiry': '5',
            'clear-cache': '2021-07-01 11:34:39'
        }
    )
    volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
    assert volume_config.cache_enabled
    assert volume_config.cache_exclude_extensions == ['jpg', 'pdf', 'txt']
    assert volume_config.cache_expiry_minutes == 5
    assert volume_config.clear_cache == datetime.datetime(2021, 7, 1, 11, 34, 39, tzinfo=pytz.UTC)


def test_worker_last_clear_cache(domains_config):
    worker_id = 'worker1'
    assert domains_config.keys.worker_last_clear_cache.get(worker_id) is None
    assert domains_config.get_worker_last_clear_cache(worker_id) is None
    dt = datetime.datetime(2021, 7, 1, 10, 12, 33, tzinfo=pytz.UTC)
    domains_config.set_worker_last_clear_cache(worker_id, dt)
    assert domains_config.get_worker_last_clear_cache(worker_id) == dt
    assert domains_config.keys.worker_last_clear_cache.get(worker_id) == b'20210701T101233'


def test_get_volume_config_challenge_attributes(domains_config):
    worker_id, hostname = 'worker1', 'worker1.com'
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = get_volume_config_dict(
        worker_id=worker_id, hostname=hostname, with_ssl=True, additional_hostnames=[
            {
                'hostname': 'hostname2.com', 'payload': 'zzPAYLOADyy', 'token': 'aaTOKENbb'
            }
        ]
    )
    volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
    assert hostname not in volume_config.hostname_challenges
    assert volume_config.hostname_challenges['hostname2.com'] == {'token': 'aaTOKENbb', 'payload': 'zzPAYLOADyy'}


def test_get_volume_config_ssl_chain(domains_config):
    worker_id, hostname = 'worker1', 'worker1.com'
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id)] = get_volume_config_dict(
        worker_id=worker_id, hostname=hostname, with_ssl={
            'privateKey': CERTIFICATE_KEY,
            'fullChain': [*CERTIFICATE_PEM, *INTERMEDIATE_CERTIFICATES],
            'chain': INTERMEDIATE_CERTIFICATES
        }
    )
    volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
    assert volume_config.hostname_certs[hostname] == {
        'privkey': "\n".join(CERTIFICATE_KEY),
        'fullchain': "\n".join([*CERTIFICATE_PEM, *INTERMEDIATE_CERTIFICATES]),
        'chain': "\n".join(INTERMEDIATE_CERTIFICATES)
    }


def test_volume_config_invalid_zone_for_cluster(domains_config):
    worker_id = 'ab123456'
    # operator is running in zone config.CWM_ZONE (EU)
    operator_zone = config.CWM_ZONE
    operator_zone_hostname = '{}.{}.{}'.format(worker_id, operator_zone.lower(), config.AWS_ROUTE53_HOSTEDZONE_DOMAIN)
    # instance is in a different zone (VO)
    instance_zone = 'VO'
    instance_zone_hostname = '{}.{}.{}'.format(worker_id, instance_zone.lower(), config.AWS_ROUTE53_HOSTEDZONE_DOMAIN)
    assert instance_zone != config.CWM_ZONE
    assert instance_zone.lower() not in map(str.lower, config.CWM_ADDITIONAL_ZONES)
    # request is made to geo hostname
    geo_hostname = '{}.geo.{}'.format(worker_id, config.AWS_ROUTE53_HOSTEDZONE_DOMAIN)
    domains_config._cwm_api_volume_configs['hostname:{}'.format(geo_hostname)] = get_volume_config_dict(
        worker_id=worker_id, hostname=instance_zone_hostname,
        additional_hostnames=[
            {'hostname': operator_zone_hostname},
            {'hostname': geo_hostname},
        ],
        additional_volume_config={
            'zone': instance_zone
        }
    )
    volume_config = domains_config.get_cwm_api_volume_config(hostname=geo_hostname)
    assert volume_config.zone_hostname == instance_zone_hostname
    assert volume_config.primary_hostname == instance_zone_hostname
    assert volume_config.geo_hostname == geo_hostname
    assert not volume_config.is_valid_zone_for_cluster
    assert volume_config.gateway_updated_for_request_hostname == geo_hostname
    assert isinstance(volume_config.gateway, VolumeConfigGatewayTypeS3)
