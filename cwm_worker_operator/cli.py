import sys

from cwm_worker_operator import initializer
from cwm_worker_operator import deployer
from cwm_worker_operator import waiter
from cwm_worker_operator import deleter


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
            delete_namespace = "--delete-namespace" in sys.argv
            deleter.delete(domain_name, deployment_timeout_string=deployment_timeout_string, delete_namespace=delete_namespace)
        else:
            raise Exception("Invalid deleter command: {}".format(" ".join(sys.argv[2:])))
    else:
        raise Exception("Invalid command: {}".format(" ".join(sys.argv[1:])))
