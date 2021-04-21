import re
import datetime

import pytz


def now():
    return datetime.datetime.now(pytz.UTC)


def strptime(value, dateformat):
    return datetime.datetime.strptime(value + 'z+0000', dateformat+'z%z')


def bytes_to_gib(bytes, ndigits=2):
    return round(bytes / 1024 / 1024 / 1024, ndigits)


def assert_valid_worker_id(worker_id):
    assert 0 < len(worker_id) <= 10 and re.match('^[0-9a-zA-Z]*$', worker_id) is not None, 'invalid worker_id: {}'.format(worker_id)


def get_namespace_name_from_worker_id(worker_id):
    assert_valid_worker_id(worker_id)
    namespace_name = worker_id
    return namespace_name


def get_worker_id_from_namespace_name(namespace_name):
    worker_id = namespace_name
    assert_valid_worker_id(worker_id)
    return worker_id
