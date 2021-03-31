import datetime

import pytz


def now():
    return datetime.datetime.now(pytz.UTC)


def strptime(value, dateformat):
    return datetime.datetime.strptime(value + 'z+0000', dateformat+'z%z')


def bytes_to_gib(bytes, ndigits=2):
    return round(bytes / 1024 / 1024 / 1024, ndigits)
