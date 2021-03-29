import os
import sys

from cwm_worker_operator import initializer
from cwm_worker_operator import deployer
from cwm_worker_operator import waiter
from cwm_worker_operator import deleter
from cwm_worker_operator import updater
from cwm_worker_operator import metrics_updater
from cwm_worker_operator import web_ui
from cwm_worker_operator import disk_usage_updater


def main():
    if sys.argv[1] == "initializer":
        if sys.argv[2] == "start_daemon":
            initializer.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid initializer command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == "deployer":
        if sys.argv[2] == "start_daemon":
            deployer.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid deployer command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == "waiter":
        if sys.argv[2] == "start_daemon":
            waiter.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid waiter command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == "deleter":
        if sys.argv[2] == "delete":
            domain_name = sys.argv[3] if len(sys.argv) >= 4 else None
            deployment_timeout_string = sys.argv[4] if len(sys.argv) >= 5 else None
            with_metrics = True if os.environ.get('CLI_DELETER_DELETE_WITH_METRICS') == 'yes' else False
            deleter.delete(domain_name, deployment_timeout_string=deployment_timeout_string, with_metrics=with_metrics)
        elif sys.argv[2] == "start_daemon":
            deleter.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid deleter command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == "updater":
        if sys.argv[2] == "start_daemon":
            updater.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid updater command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == "metrics-updater":
        if sys.argv[2] == "start_daemon":
            metrics_updater.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid metrics-updater command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == 'web-ui':
        if sys.argv[2] == 'start_daemon':
            web_ui.start_daemon()
    elif sys.argv[1] == "disk-usage-updater":
        if sys.argv[2] == "start_daemon":
            disk_usage_updater.start_daemon('--once' in sys.argv)
        else:
            raise Exception("Invalid disk-usage-updater command: {}".format(" ".join(sys.argv[2:])))
    else:
        raise Exception("Invalid command: {}".format(" ".join(sys.argv[1:])))
