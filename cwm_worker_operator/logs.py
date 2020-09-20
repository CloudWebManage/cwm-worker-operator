import datetime

from cwm_worker_operator import config


def debug_info(msg, **kwargs):
    debug(msg, debug_verbosity=1, **kwargs)


def debug(msg, debug_verbosity=5, start_time=None, **kwargs):
    if config.DEBUG and config.DEBUG_VERBOSITY >= debug_verbosity:
        if start_time:
            kwargs["duration"] = (datetime.datetime.now() - start_time).total_seconds()
        if len(kwargs) > 0:
            msg = "{} ({})".format(msg, " ".join(["{}={}".format(k, v) for k, v in kwargs.items()]))
        print(msg, flush=True)
