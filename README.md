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

Set env vars

```
export DEBUG=yes
export REDIS_HOST=172.17.0.1
export CWM_ZONE=EU
```

Set secret env vars (you can get them from Jenkins):

```
export CWM_API_URL=
export PACKAGES_READER_GITHUB_USER=
export PACKAGES_READER_GITHUB_TOKEN=
```

### Build Docker image

The docker image should be built to be available in the minikube environment

```
eval $(minikube -p minikube docker-env) &&\
docker build -t docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest .
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

Run a tests with full output, by specifying part of the test method name

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
