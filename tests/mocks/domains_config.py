from copy import deepcopy

from cwm_worker_operator import domains_config
from cwm_worker_operator import common

from ..common import get_volume_config_json


class MockDomainsConfig(domains_config.DomainsConfig):
    _dc = domains_config

    def __init__(self):
        self._cwm_api_volume_configs = {}
        super(MockDomainsConfig, self).__init__()

    def _cwm_api_volume_config_api_call(self, query_param, query_value):
        return deepcopy(self._cwm_api_volume_configs['{}:{}'.format(query_param, query_value)])

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
                if blank_keys and key.decode() in blank_keys:
                    all_values[key.decode()] = ""
                elif key == b'alerts':
                    values = []
                    while True:
                        value = r.lpop(key)
                        if value is None:
                            break
                        else:
                            values.append(value.decode())
                    all_values[key.decode()] = ' | '.join(values)
                else:
                    all_values[key.decode()] = r.get(key).decode()
        return all_values

    def _set_mock_volume_config(self, worker_id='worker1', hostname='example002.com', **kwargs):
        self.keys.volume_config.set(worker_id, get_volume_config_json(worker_id=worker_id, hostname=hostname, **kwargs))
        return worker_id, hostname, common.get_namespace_name_from_worker_id(worker_id)
