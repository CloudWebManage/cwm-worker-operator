import os
import shutil
import datetime

import pytest

from cwm_worker_operator import common, config


def test_valid_namespace_names():
    for worker_id, expected_namespace_name in {
        'example007com': 'cwm-worker-example007com',
        'Example007com': 'cwm-worker-e-example007com',
        'Example007coM': 'cwm-worker-e-example007com-m',
        'eXe': 'cwm-worker-ex-xe',
        ''.join(['a' for _ in range(242)]): 'cwm-worker-' + ''.join(['a' for _ in range(242)]),
        'a': 'cwm-worker-a',
        'aa': 'cwm-worker-aa',
        ''.join(['A' for _ in range(80)]): 'cwm-worker-' + ''.join(['a-a' for _ in range(80)]),
        '0aaa0': 'cwm-worker-0aaa0',
    }.items():
        assert common.get_namespace_name_from_worker_id(worker_id) == expected_namespace_name
        common.assert_valid_namespace_name(expected_namespace_name)
        assert common.get_worker_id_from_namespace_name(expected_namespace_name) == worker_id


def test_invalid_namespace_names():
    for worker_id in [
        '-',
        '.foo.',
        '.foo',
        'foo.',
        'foo$foo',
        ''.join(['a' for _ in range(254)]),
        ''.join(['A' for _ in range(85)]),
        'example007.com',
    ]:
        with pytest.raises(Exception):
            common.assert_valid_worker_id(worker_id)
        with pytest.raises(Exception):
            common.assert_valid_namespace_name(common.get_namespace_name_from_worker_id(worker_id))


def test_local_storage_json_last_items():
    key = 'tests/json_last_items'
    shutil.rmtree(os.path.join(config.LOCAL_STORAGE_PATH, key), ignore_errors=True)
    now = common.now()
    for i in range(100):
        common.local_storage_json_last_items_append(
            key, {'i': i}, max_items=5,
            now_=now + datetime.timedelta(seconds=i)
        )
    assert list(common.local_storage_json_last_items_iterator(key, max_items=3)) == [
        {
            'item': {'i': i},
            'datetime': common.strptime((now + datetime.timedelta(seconds=i)).strftime('%Y-%m-%dT%H-%M-%S'), '%Y-%m-%dT%H-%M-%S')
        }
        for i in [99, 98, 97]
    ]
    assert list(common.local_storage_json_last_items_iterator(key)) == [
        {
            'item': {'i': i},
            'datetime': common.strptime((now + datetime.timedelta(seconds=i)).strftime('%Y-%m-%dT%H-%M-%S'), '%Y-%m-%dT%H-%M-%S')
        }
        for i in [99, 98, 97, 96, 95]
    ]
