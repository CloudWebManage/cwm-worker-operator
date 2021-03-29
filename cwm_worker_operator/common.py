import datetime

import pytz


def now():
    return datetime.datetime.now(pytz.UTC)


def strptime(value, dateformat):
    return datetime.datetime.strptime(value + 'z+0000', dateformat+'z%z')
