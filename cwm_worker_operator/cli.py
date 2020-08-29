import sys

from cwm_worker_operator import deployer
from cwm_worker_operator import errorhandler


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
    else:
        raise Exception("Invalid command: {}".format(" ".join(sys.argv[1:])))
