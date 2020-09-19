#!/usr/bin/env bash

echo starting docker tests &&\
tests/clear_deployments.sh &&\
tests/redis_start.sh &&\
echo testing deployer - valid domain &&\
DOMAIN=example007.com &&\
NAMESPACE=example007--com &&\
tests/redis_clear.sh "${DOMAIN}" &&\
tests/namespace_clear.sh "${NAMESPACE}" &&\
echo Starting initializer daemon &&\
docker run -d --name initializer --rm \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -e DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS \
    -p 8081:8081 \
    cwm_worker_operator initializer start_daemon &&\
echo Starting deployer daemon &&\
docker run -d --name deployer --rm \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -e DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS \
    -p 8082:8082 \
    cwm_worker_operator deployer start_daemon &&\
echo Starting waiter daemon &&\
docker run -d --name waiter --rm \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -e DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS \
    -e WAITER_VERIFY_WORKER_ACCESS=no \
    -p 8083:8083 \
    cwm_worker_operator waiter start_daemon &&\
echo Requesting initialization of valid domain "${DOMAIN}" &&\
redis-cli set "worker:initialize:${DOMAIN}" "" &&\
echo Waiting for domain to be available &&\
tests/wait_for.sh "
  [ \"\$(redis-cli --raw exists \"worker:available:${DOMAIN}\")\" == \"1\" ] &&\
  [ \"\$(redis-cli --raw get \"worker:ingress:hostname:${DOMAIN}\")\" == \"minio.${NAMESPACE}.svc.cluster.local\" ]
" "30" "waited too long for domain to be available" &&\
echo testing deployer - invalid domain &&\
DOMAIN=invalid.domain &&\
NAMESPACE=invalid--domain &&\
tests/redis_clear.sh "${DOMAIN}" &&\
tests/namespace_clear.sh "${NAMESPACE}" &&\
echo Requesting initialization of invalid domain "${DOMAIN}" &&\
redis-cli set "worker:initialize:${DOMAIN}" "" &&\
echo Waiting for domain to be errored &&\
tests/wait_for.sh "
  [ \"\$(redis-cli --raw exists \"worker:error:${DOMAIN}\")\" == \"1\" ]
" "30" "waited too long for domain to be errored" &&\
echo testing metrics &&\
curl -s localhost:8081 | grep 'initializer_request_latency_count{domain="",status="initialized"} 1.0' &&\
curl -s localhost:8082 | grep 'volume_config_fetch_latency_count{domain="",status="success_cache"} 1.0' &&\
curl -s localhost:8082 | grep 'deployer_request_latency_count{domain="",status="success"} 1.0' &&\
curl -s localhost:8083 | grep 'waiter_request_latency_count{domain="",status="success"} 1.0' &&\
echo docker tests completed successfully &&\
docker rm -f initializer &&\
docker rm -f deployer &&\
docker rm -f waiter &&\
docker rm -f redis &&\
exit 0
