import os
import json

from cwm_worker_operator import domains_config
from cwm_worker_operator import common


def get_ssl_keys(name):
    key_filename = 'tests/mocks/{}.key'.format(name)
    pem_filename = 'tests/mocks/{}.pem'.format(name)
    if not os.path.exists(key_filename) or not os.path.exists(pem_filename):
        key_filename = 'tests/mocks/example002.com.key'
        pem_filename = 'tests/mocks/example002.com.pem'
    with open(key_filename) as key_f:
        with open(pem_filename) as pem_f:
            return {'key': key_f.read(), 'pem': pem_f.read()}


class MockDomainsConfig(domains_config.DomainsConfig):
    _dc = domains_config

    def __init__(self):
        self._cwm_api_volume_configs = {}
        super(MockDomainsConfig, self).__init__()

    def _cwm_api_volume_config_api_call(self, query_param, query_value):
        return self._cwm_api_volume_configs['{}:{}'.format(query_param, query_value)]

    # test utility functions

    def _iterate_redis_pools(self):
        for pool in ['ingress', 'internal', 'metrics']:
            with getattr(self, 'get_{}_redis'.format(pool))() as r:
                yield r

    def _get_all_redis_pools_keys(self):
        all_keys = set()
        for r in self._iterate_redis_pools():
            for key in r.keys("*"):
                assert key not in all_keys, 'duplicate key between redis pools: {}'.format(key)
                all_keys.add(key.decode())
        return all_keys

    def _get_all_redis_pools_values(self, blank_keys=None):
        all_values = {}
        for r in self._iterate_redis_pools():
            for key in r.keys("*"):
                assert key not in all_values, 'duplicate key between redis pools: {}'.format(key)
                all_values[key.decode()] = "" if blank_keys and key.decode() in blank_keys else r.get(key).decode()
        return all_values

    def _set_mock_volume_config(self, worker_id='worker1', hostname='example002.com', with_ssl=False, additional_hostnames=None):
        if not additional_hostnames:
            additional_hostnames = []
        self.keys.volume_config.set(worker_id, json.dumps({
            'id': worker_id,
            'hostnames': [
                {'hostname': hostname, **(get_ssl_keys(hostname) if with_ssl else {})},
                *additional_hostnames
            ]
        }))
        return worker_id, hostname, common.get_namespace_name_from_worker_id(worker_id)
