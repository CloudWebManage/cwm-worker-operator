import sys

from cwm_worker_operator import deployer
from cwm_worker_operator import errorhandler
from cwm_worker_operator import deleter


def main():
    if sys.argv[1] == "deployer":
        if sys.argv[2] == "start":
            once = '--once' in sys.argv
            deployer.start(once=once)
        else:
            raise Exception("Invalid deployer command: {}".format(" ".join(sys.argv[2:])))
    elif sys.argv[1] == "errorhandler":
        if sys.argv[2] == "start":
            once = '--once' in sys.argv
            errorhandler.start(once=once)
        else:
            raise Exception("Invalid errorhandler command: {}".format(" ".join(sys.argv[2:])))
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
