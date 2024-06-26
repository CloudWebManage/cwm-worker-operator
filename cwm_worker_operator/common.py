import re
import os
import json
import datetime
from glob import glob
from functools import lru_cache

import pytz

from . import config


UPPERCASE_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWERCASE_LETTERS_AND_NUMBERS = '0123456789abcdefghijklmnopqrstuvwxyz'


def now():
    return datetime.datetime.now(pytz.UTC)


def strptime(value, dateformat):
    if '+' in value:
        # value already has a timezone specifier
        return datetime.datetime.strptime(value, dateformat + '%z')
    else:
        # value does not have a timezone specifier, we assume utc
        return datetime.datetime.strptime(value + 'z+0000', dateformat+'z%z')


def bytes_to_gib(bytes, ndigits=2):
    return round(bytes / 1024 / 1024 / 1024, ndigits)


@lru_cache(maxsize=9999)
def assert_valid_worker_id(worker_id):
    assert_valid_namespace_name(get_namespace_name_from_worker_id(worker_id))


@lru_cache(maxsize=9999)
def assert_valid_namespace_name(namespace_name):
    assert 0 < len(namespace_name) <= 253 and re.match('^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', namespace_name) is not None, 'invalid namespace_name: {}'.format(namespace_name)


class InvalidWorkerIdException(Exception):
    pass


@lru_cache(maxsize=9999)
def get_namespace_name_from_worker_id(worker_id):
    namespace_name = 'cwm-worker-'
    for char in worker_id:
        if char in UPPERCASE_LETTERS:
            namespace_name += char.lower() + '-' + char.lower()
        elif char in LOWERCASE_LETTERS_AND_NUMBERS:
            namespace_name += char
        else:
            raise InvalidWorkerIdException("Invalid worker_id, '{}' is not allowed: {}".format(char, worker_id))
    return namespace_name


@lru_cache(maxsize=9999)
def get_worker_id_from_namespace_name(namespace_name):
    worker_id = namespace_name.replace('cwm-worker-', '')
    for char in UPPERCASE_LETTERS:
        worker_id = worker_id.replace(char.lower() + '-' + char.lower(), char)
    return worker_id


@lru_cache(maxsize=9999)
def get_namespace_name_from_bucket_name(bucket_name):
    if is_worker_namespace(bucket_name):
        return bucket_name
    else:
        return None


def is_worker_namespace(namespace_name):
    return (
        namespace_name.startswith('cwm-worker-')
        and namespace_name not in [
            'cwm-worker-ingress',
            'cwm-worker-operator-nas-checker',
        ]
    )


def is_hostnames_match(full_hostname, partial_hostname):
    if full_hostname.lower() == partial_hostname.lower():
        return True
    elif '.'.join(full_hostname.split('.')[1:]).lower() == partial_hostname.lower():
        return True
    else:
        return False


def is_hostnames_match_in_list(full_hostname, partial_hostnames):
    return any((is_hostnames_match(full_hostname, partial_hostname) for partial_hostname in partial_hostnames))


def dicts_merge(*dicts):
    res = {}
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, dict) and isinstance(res.get(k), dict):
                res[k] = dicts_merge(res[k], v)
            else:
                res[k] = v
    return res


def local_storage_set(filename: str, content: str):
    fullpath = os.path.join(config.LOCAL_STORAGE_PATH, filename)
    dirname = os.path.dirname(fullpath)
    if not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    temp_fullpath = fullpath + '.temp'
    with open(temp_fullpath, 'w') as f:
        f.write(content)
    os.rename(temp_fullpath, fullpath)


def local_storage_json_set(key: str, value: dict):
    local_storage_set('{}.json'.format(key), json.dumps(value))


def local_storage_json_last_items_append(key: str, value: dict, max_items=20, now_=None):
    if not now_:
        now_ = now()
    filekey = now_.strftime('%Y-%m-%dT%H-%M-%S')
    local_storage_json_set(os.path.join(key, filekey), value)
    items = sorted(glob(os.path.join(config.LOCAL_STORAGE_PATH, key, '*')), reverse=True)
    if len(items) > max_items:
        os.unlink(items[-1])


def local_storage_json_last_items_iterator(key: str, max_items=None):
    for i, filename in enumerate(sorted(glob(os.path.join(config.LOCAL_STORAGE_PATH, key, '*.json')), reverse=True)):
        if max_items and i >= max_items:
            break
        with open(filename) as f:
            yield {
                'datetime': strptime(filename.replace(os.path.join(config.LOCAL_STORAGE_PATH, key) + '/', '').replace('.json', ''), '%Y-%m-%dT%H-%M-%S'),
                'item': json.load(f)
            }
