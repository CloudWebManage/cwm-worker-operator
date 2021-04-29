import re
import datetime
from functools import lru_cache

import pytz


UPPERCASE_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWERCASE_LETTERS_AND_NUMBERS = '0123456789abcdefghijklmnopqrstuvwxyz'


def now():
    return datetime.datetime.now(pytz.UTC)


def strptime(value, dateformat):
    return datetime.datetime.strptime(value + 'z+0000', dateformat+'z%z')


def bytes_to_gib(bytes, ndigits=2):
    return round(bytes / 1024 / 1024 / 1024, ndigits)


@lru_cache(maxsize=9999)
def assert_valid_worker_id(worker_id):
    assert_valid_namespace_name(get_namespace_name_from_worker_id(worker_id))


@lru_cache(maxsize=9999)
def assert_valid_namespace_name(namespace_name):
    assert 0 < len(namespace_name) <= 253 and re.match('^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', namespace_name) is not None, 'invalid namespace_name: {}'.format(namespace_name)


@lru_cache(maxsize=9999)
def get_namespace_name_from_worker_id(worker_id):
    namespace_name = ''
    for char in worker_id:
        if char in UPPERCASE_LETTERS:
            namespace_name += char.lower() + '-' + char.lower()
        elif char in LOWERCASE_LETTERS_AND_NUMBERS:
            namespace_name += char
        else:
            raise Exception("Invalid worker_id, '{}' is not allowed: {}".format(char, worker_id))
    return namespace_name


@lru_cache(maxsize=9999)
def get_worker_id_from_namespace_name(namespace_name):
    worker_id = namespace_name
    for char in UPPERCASE_LETTERS:
        worker_id = worker_id.replace(char.lower() + '-' + char.lower(), char)
    return worker_id
