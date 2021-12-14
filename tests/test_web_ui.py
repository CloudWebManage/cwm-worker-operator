import json

from cwm_worker_operator import web_ui


class MockServer:

    def __init__(self, domains_config):
        self.dc = domains_config


def test_hostname_api(domains_config):
    server = MockServer(domains_config)
    hostname = 'test.example.com'
    domains_config.keys.hostname_available.set(hostname, '')
    domains_config.keys.hostname_error.set(hostname, 'FAILED_TO_DEPLOY')
    domains_config.keys.hostname_error_attempt_number.set(hostname, 3)
    domains_config.keys.hostname_ingress_hostname.set(hostname, json.dumps({'foo': 'bar'}))
    domains_config.keys.volume_config_hostname_worker_id.set(hostname, 'foobar')
    domains_config.keys.hostname_initialize.set(hostname, '')
    res = list(web_ui.get_hostname(True, server, hostname))
    assert res == [
        {'header': True,
         'hostname': '/api/hostname/<HOSTNAME>',
         'index': '/api/',
         'nodes': '/api/nodes',
         'redis key': '/api/redis_key/<POOL>/<REDIS_KEY>',
         'worker': '/api/worker/<WORKER_ID>'},
        {'keys': [{'hostname:available:test.example.com': ''}],
         'title': 'hostname_available',
         'total': 1},
        {'keys': [{'hostname:error:test.example.com': 'FAILED_TO_DEPLOY'}],
         'title': 'hostname_error',
         'total': 1},
        {'keys': [{'hostname:error_attempt_number:test.example.com': '3'}],
         'title': 'hostname_error_attempt_number',
         'total': 1},
        {'keys': [{'hostname:ingress:hostname:test.example.com': '{"foo": "bar"}'}],
         'title': 'hostname_ingress_hostname',
         'total': 1},
        {'keys': [{'hostname:initialize:test.example.com': ''}],
         'title': 'hostname_initialize',
         'total': 1},
        {'keys': [{'hostname:last_deployment_flow:action:test.example.com': None}],
         'title': 'hostname_last_deployment_flow_action',
         'total': 0},
        {'keys': [{'hostname:last_deployment_flow:time:test.example.com': None}],
         'title': 'hostname_last_deployment_flow_time',
         'total': 0},
        {'keys': [{'worker:volume:config:hostname_worker_id:test.example.com': 'foobar'}],
         'title': 'volume_config_hostname_worker_id',
         'total': 1},
        {'delete all hostname keys': '/api/hostname/delete/test.example.com',
         'footer': True},
    ]
    for data in res:
        json.dumps(data).encode()
