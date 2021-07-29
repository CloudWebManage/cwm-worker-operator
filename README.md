# cwm-worker-operator

![CI](https://github.com/CloudWebManage/cwm-worker-operator/workflows/CI/badge.svg?branch=main&event=push)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/CloudWebManage/cwm-worker-operator)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/CloudWebManage/cwm-worker-operator/blob/main/LICENSE)

![Lines of code](https://img.shields.io/tokei/lines/github/CloudWebManage/cwm-worker-operator?label=LOC)
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/CloudWebManage/cwm-worker-operator)
![GitHub repo size](https://img.shields.io/github/repo-size/CloudWebManage/cwm-worker-operator)

- [Introduction](#introduction)
- [Local Development](#local-development)
  - [Install](#install)
  - [Start Infrastructure](#start-infrastructure)
  - [Run Tests](#run-tests)
- [Helm Chart Development](#helm-chart-development)

## Introduction

Python library and CLI for controlling the lifecycle of workloads deployed on
the CWM cluster. The main entry points are defined in the
[cli](https://github.com/CloudWebManage/cwm-worker-operator/blob/main/cwm_worker_operator/cli.py)
and include daemons that run continuously and periodically handle various
operations. After the installation, run `cwm-worker-operator --help` command to
see all the supported CLI commands. The project also includes a Helm template
used for the production deployment that runs and configures all the daemons on
the CWM k8s cluster.

## Local Development

Python 3.8.5 or later is required. If multiple Python 3 versions are available,
use 3.8.5 or later appropriately e.g. `python3.8 -m venv venv`.

### Install

Create `virtualenv`:

```shell
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install --upgrade setuptools wheel
```

Install dependencies:

```shell
venv/bin/python -m pip install -r requirements.txt
```

Install the Python module:

```shell
venv/bin/python -m pip install -e .
```

### Start Infrastructure

Start a Minikube cluster:

```shell
minikube start --driver=docker --kubernetes-version=v1.18.15
```

Make sure you are connected to the Minikube cluster:

```shell
minikube kubectl -- get nodes -A
```

Start a Redis server:

```shell
docker run -d --rm --name redis -p 6379:6379 redis
```

Create a `.env` file with the following:

```shell
export REDIS_HOST=172.17.0.1
export CWM_ZONE=EU
export CWM_ADDITIONAL_ZONES=iL,Us
export ENABLE_DEBUG=yes
export DEBUG_VERBOSITY=10
export DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS="240.0"
export CACHE_MINIO_VERSIONS=0.0.0-20200829T091900,0.0.0-20200910T100633
export WAITER_VERIFY_WORKER_ACCESS=no
```

Add secret env vars to the `.env` (you can get them from Jenkins):

```shell
export CWM_API_URL=
export PACKAGES_READER_GITHUB_USER=
export PACKAGES_READER_GITHUB_TOKEN=
export AWS_ROUTE53_HOSTEDZONE_ID=
export AWS_ROUTE53_HOSTEDZONE_DOMAIN=
export AWS_ACCESS_KEY_ID=
export AWS_SECRET_ACCESS_KEY=
```

Add the test worker ids, you can get them from cwm-worker-cluster repo at
`cwm_worker_cluster.config.LOAD_TESTING_WORKER_ID` and
`cwm_worker_cluster.config.LOAD_TESTING_GATEWAY_*`:

```shell
export TEST_WORKER_ID=
export TEST_GATEWAY_WORKER_ID=
export TEST_GATEWAY_AWS_WORKER_ID=
export TEST_GATEWAY_AZURE_WORKER_ID=
export TEST_GATEWAY_GOOGLE_WORKER_ID=
```

Source the `.env` file:

```shell
source .env
```

### Run Tests

Install test dependencies:

```shell
venv/bin/python -m pip install -r tests/requirements.txt
```

Activate the `virtualenv`:

```shell
. venv/bin/activate
```

Run all tests:

```shell
pytest
```

Run a test with the full output by specifying part of the test method name:

```shell
pytest -sk "invalid_volume_config"
```

Or by specifying the specific test file name:

```shell
pytest -s tests/test_initializer.py
```

Pytest CLI provides a lot of command-line options. For details, check its help
message or refer to [pytest documentation](https://docs.pytest.org/en/latest/).

## Helm Chart Development

Verify the connection to the Minikube cluster:

```shell
kubectl get nodes
```

Set helm arguments:

```shell
HELMARGS="--set cwm_api_url=$CWM_API_URL,packages_reader_github_user=$PACKAGES_READER_GITHUB_USER,packages_reader_github_token=$PACKAGES_READER_GITHUB_TOKEN"
```

Deploy using one of the following options:

- Use the published Docker images:

  - Create a docker pull secret:

    ```shell
    echo '{"auths":{"docker.pkg.github.com":{"auth":"'"$(echo -n "${PACKAGES_READER_GITHUB_USER}:${PACKAGES_READER_GITHUB_TOKEN}" | base64 -w0)"'"}}}' | \
      kubectl create secret generic github --type=kubernetes.io/dockerconfigjson --from-file=.dockerconfigjson=/dev/stdin
    ```

- Build your own Docker images:

  - Switch Docker daemon to use the Minikube Docker daemon:

    ```shell
    eval $(minikube -p minikube docker-env)
    ```

  - Build the image:

    ```shell
    docker build -t docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest .
    ```

Deploy:

```shell
helm upgrade --install cwm-worker-operator ./helm $HELMARGS
```

Start a port-forward to the Redis:

```shell
kubectl port-forward service/cwm-worker-operator-redis 6379
```

For more details, refer to the [CI workflow](./.github/workflows/ci.yml).
