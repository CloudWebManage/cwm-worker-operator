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

Python daemons which control the lifecycle of workloads deployed on the
CWM cluster.

See the [CLI reference](CLI.md) for details of the different daemons.

The project also includes a Helm template used for the production
deployment that runs and configures all the daemons on the CWM k8s cluster.

## Documentation

Each daemon module should include it's documentation in the module file __doc__
section. This is a string at the beginning of the file. This string is then
displayed in the [CLI reference](CLI.md).

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

source the .env file: `source .env`

Create helm values file:

```
echo "
cwm_api_url: $CWM_API_URL
cwm_api_key: $CWM_API_KEY
cwm_api_secret: $CWM_API_SECRET

operator:
  daemons: [initializer,deployer,waiter,updater,web-ui]
" > .values.yaml
```

Deploy using one of the following options:

- Use the published Docker images:

  - No additional action needed, images are public

- Build your own Docker images:

  - Switch Docker daemon to use the Minikube Docker daemon:

    ```shell
    eval $(minikube -p minikube docker-env)
    ```

  - Build the image:

    ```shell
    docker build -t ghcr.io/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest .
    ```

Deploy:

```shell
helm upgrade --install cwm-worker-operator -f .values.yaml ./helm
```

Start a port-forward to the Redis:

```shell
kubectl port-forward service/cwm-worker-operator-redis-internal 6379
```

For more details, refer to the [CI workflow](./.github/workflows/ci.yml).

## Local Development on real cluster

Follow the steps in Local Development section until Start Infrastructure, then continue with the following steps:

```shell
# Set the cluster env vars depending on the cluster you want to connect to, you should only use dev / testing clusters
export CLUSTER_NAME=cwmc-eu-v2test
export CWM_ZONE=eu-test
export DNS_RECORDS_PREFIX=$CLUSTER_NAME

# Get a fresh token from Vault
export VAULT_TOKEN=

cd ../cwm-worker-cluster
eval "$(venv/bin/cwm-worker-cluster cluster connect $CLUSTER_NAME)"
popd >/dev/null

# Optionally, enable full verbosity debugging
export DEBUG=yes
export DEBUG_VERBOSITY=10

# Set env vars to point to the Redis databases (we will start port-forwarding later)
export INGRESS_REDIS_PORT=6381
export INTERNAL_REDIS_PORT=6382
export METRICS_REDIS_PORT=6383
export INTERNAL_REDIS_DB=0
export METRICS_REDIS_DB=0
```

Start port-forwarding to the Redis databases (you can run this multiple times if a forward was stopped):

```shell
lsof -i:6381 >/dev/null || kubectl -n cwm-worker-ingress port-forward service/cwm-worker-ingress-operator-redis 6381:6379 >/dev/null 2>&1 &
lsof -i:6382 >/dev/null || kubectl -n cwm-operator port-forward service/cwm-worker-operator-redis-internal 6382:6379 >/dev/null 2>&1 &
lsof -i:6383 >/dev/null || kubectl -n cwm-operator port-forward service/cwm-worker-operator-redis-metrics 6383:6379 >/dev/null 2>&1 &
```

Stop the relevant operator daemones running on the cluster to prevent conflicts. First, disable argocd autosync,
then scale the relevant deployments to 0, for example:

```shell
kubectl -n cwm-operator scale deployment deployer --replicas=0
```

Now you can run operator commands for the relevant daemons, for example:

```
cwm-worker-operator deployer start_daemon --once
```

When done, terminate the background jobs:

```
kill $(jobs -p)
```
