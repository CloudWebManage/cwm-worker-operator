import json
import datetime
from collections import defaultdict

from cwm_worker_operator import config


class Metrics:

    def __init__(self, group):
        self.metrics = defaultdict(int)
        self.group = group
        self.last_save_time = self.start_time = datetime.datetime.now()

    def send(self, metric, **debug_data):
        self.metrics[metric] += 1
        if config.DEBUG:
            print("{}: {}".format(metric, debug_data), flush=True)

    def save(self, force=False):
        now = datetime.datetime.now()
        if force or (now - self.last_save_time).total_seconds() >= config.METRICS_SAVE_INTERVAL_SECONDS:
            self.last_save_time = now
            with open("{}.{}".format(config.METRICS_SAVE_PATH_PREFIX, self.group), "a") as f:
                json.dump({
                    "uptime": (datetime.datetime.now() - self.start_time).total_seconds(),
                    **dict(self.metrics)
                }, f)
                f.write("\n")
