from contextlib import contextmanager

from cwm_worker_operator import config
from cwm_worker_operator import common


def debug_info(msg, **kwargs):
    debug(msg, debug_verbosity=1, **kwargs)


def debug(msg, debug_verbosity=5, start_time=None, **kwargs):
    if config.DEBUG and config.DEBUG_VERBOSITY >= debug_verbosity:
        if start_time:
            kwargs["duration"] = (common.now() - start_time).total_seconds()
        if len(kwargs) > 0:
            msg = "{} ({})".format(msg, " ".join(["{}={}".format(k, v) for k, v in kwargs.items()]))
        print(msg, flush=True)


def alert(domains_config, msg, **kwargs):
    debug_info("ALERT: {}".format(msg), **kwargs)
    domains_config.alerts_push({"type": "cwm-worker-operator-logs", "msg": msg, "kwargs": kwargs})


@contextmanager
def alert_exception_catcher(domains_config, **kwargs):
    try:
        yield
    except Exception as e:
        alert(domains_config, "exception: {}".format(str(e)), **kwargs)
        raise
