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

### Usage

Activate the virtualenv

```
. venv/bin/activate
```

Make sure you are connected to a local / testing Kubernetes cluster

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
export CWM_API_URL=
export CWM_ZONE=EU
export PACKAGES_READER_GITHUB_USER=
export PACKAGES_READER_GITHUB_TOKEN=
```

Set a real worker domain for testing

```
DOMAIN=example007.com
```

Set the real domains and some invalid domains to initialize

```
redis-cli set "worker:initialize:${DOMAIN}" "" &&\
redis-cli set "worker:initialize:invalid.domain" "" &&\
redis-cli set "worker:initialize:invalid.domain2" ""
```

Run a single iteration of initializer, deployer, waiter

```
cwm_worker_operator initializer start_daemon --once &&\
cwm_worker_operator deployer start_daemon --once &&\
cwm_worker_operator waiter start_daemon --once
```

Run tests

```
tests/run_tests.sh
```

## Docker image development

Build and start the initializer, deployer and waiter daemons, using env vars from the local dev + minikube:

```
docker build -t cwm_worker_operator . &&\
docker run -d \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -p 8081:8081 \
    cwm_worker_operator initializer start_daemon &&\
docker run -d \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -p 8082:8082 \
    cwm_worker_operator deployer start_daemon &&\
docker run -d \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -p 8083:8083 \
    cwm_worker_operator waiter start_daemon
```

Test a valid domain

```
DOMAIN=example007.com
kubectl delete ns example007--com;
sleep 2
tests/redis_clear.sh "${DOMAIN}" &&\
redis-cli set "worker:initialize:${DOMAIN}" ""
```

After a couple of seconds, check it's status and get the internal hostname

```
[ "$(redis-cli --raw exists "worker:available:${DOMAIN}")" == "1" ] &&\
[ "$(redis-cli --raw get "worker:ingress:hostname:${DOMAIN}")" == "minio.example007--com.svc.cluster.local" ]
```

Test an invalid domain

```
DOMAIN=invalid.domain
kubectl delete ns invalid--domain;
sleep 2
tests/redis_clear.sh "${DOMAIN}" &&\
redis-cli set "worker:initialize:${DOMAIN}" ""
```

After a couple of seconds, check it's error status

```
[ "$(redis-cli --raw exists "worker:error:${DOMAIN}")" == "1" ]
```

Set a volume config for this domain

```
redis-cli set "worker:volume:config:${DOMAIN}" '{"hostname":"invalid.domain","zone":"EU"}'
```

Check metrics

* http://localhost:8081
* http://localhost:8082
* http://localhost:8083

## Helm chart development

Create a cluster

```
minikube start --driver=docker --kubernetes-version=v1.16.14
```

Verify connection to the cluster

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

Run k8s tests

```
tests/k8s_tests.sh
```