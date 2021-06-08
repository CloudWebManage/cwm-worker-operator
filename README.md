# cwm-worker-operator

## Local development

### Install

Create virtualenv

```
python3 -m venv venv
```

Install dependencies

```
venv/bin/python -m pip install -r requirements.txt
```

Install the Python module

```
venv/bin/python -m pip install -e .
```

### Start infrastructure

start a Minikube cluster

```
bin/minikube_start.sh && bin/minikube_wait.sh
``` 

Make sure you are connected to the minikube cluster

```
kubectl get nodes
```

Start a Redis server

```
docker run -d --rm --name redis -p 6379:6379 redis
```

Create a `.env` file with the following:

```
export REDIS_HOST=172.17.0.1
export CWM_ZONE=EU
export CWM_ADDITIONAL_ZONES=iL,Us
export ENABLE_DEBUG=yes
export DEBUG_VERBOSITY=10
export DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS="120.0"
export CACHE_MINIO_VERSIONS=0.0.0-20200829T091900,0.0.0-20200910T100633
export WAITER_VERIFY_WORKER_ACCESS=no
```

Add secret env vars to the `.env` (you can get them from Jenkins):

```
export CWM_API_URL=
export PACKAGES_READER_GITHUB_USER=
export PACKAGES_READER_GITHUB_TOKEN=
export AWS_ROUTE53_HOSTEDZONE_ID=
export AWS_ROUTE53_HOSTEDZONE_DOMAIN=
export AWS_ACCESS_KEY_ID=
export AWS_SECRET_ACCESS_KEY=
```

Add the test worker ids, you can get them from cwm-worker-cluster repo at `cwm_worker_cluster.config.LOAD_TESTING_WORKER_ID` and `cwm_worker_cluster.config.LOAD_TESTING_GATEWAY_WORKER_ID`

```
export TEST_WORKER_ID=
export TEST_GATEWAY_WORKER_ID=
```

Source the `.env` file

```
source .env
```

### Run tests

Activate the virtualenv

```
. venv/bin/activate
```

Run all tests

```
pytest
```

Run a test with full output, by specifying part of the test method name

```
pytest -sk "invalid_volume_config"
```

Or by specifying the specific test file name:

```
pytest -s tests/test_initializer.py
```

Pytest has many options, check the help message or [pytest documentation](https://docs.pytest.org/en/latest/) for details

## Helm chart development

Verify connection to the minikube cluster

```
kubectl get nodes
```

Set helm arguments

```
HELMARGS="--set cwm_api_url=$CWM_API_URL,packages_reader_github_user=$PACKAGES_READER_GITHUB_USER,packages_reader_github_token=$PACKAGES_READER_GITHUB_TOKEN"
```

Deploy using one of the following options:

* Use the published Docker images:
  * Create a docker pull secret
    * `echo '{"auths":{"docker.pkg.github.com":{"auth":"'"$(echo -n "${PACKAGES_READER_GITHUB_USER}:${PACKAGES_READER_GITHUB_TOKEN}" | base64 -w0)"'"}}}' | kubectl create secret generic github --type=kubernetes.io/dockerconfigjson --from-file=.dockerconfigjson=/dev/stdin`

* Build your own Docker images:
  * Switch Docker daemon to use the minikube Docker daemon: `eval $(minikube -p minikube docker-env)`
  * Build the image: `docker build -t docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest .`
  
Deploy

```
helm upgrade --install cwm-worker-operator ./helm $HELMARGS
```

Start a port-forward to the redis

```
kubectl port-forward service/cwm-worker-operator-redis 6379
```
