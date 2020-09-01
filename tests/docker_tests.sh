#!/usr/bin/env bash

echo starting docker tests &&\
tests/clear_deployments.sh &&\
tests/redis_start.sh &&\
echo testing deployer - valid domain &&\
DOMAIN=example007.com &&\
NAMESPACE=example007--com &&\
tests/redis_clear.sh "${DOMAIN}" &&\
tests/namespace_clear.sh "${NAMESPACE}" &&\
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
    -e ERRORHANDLER_WAIT_DEPLOYMENT_READY_MAX_SECONDS \
    cwm_worker_operator deployer start &&\
echo Requesting initialization of valid domain "${DOMAIN}" &&\
redis-cli set "worker:initialize:${DOMAIN}" "" &&\
echo Waiting for domain to be available &&\
tests/wait_for.sh "
  [ \"\$(redis-cli --raw exists \"worker:available:${DOMAIN}\")\" == \"1\" ] &&\
  [ \"\$(redis-cli --raw get \"worker:ingress:hostname:${DOMAIN}\")\" == \"minio.${NAMESPACE}.svc.cluster.local\" ]
" "30" "waited too long for domain to be available" &&\
echo testing deployer - invalid domain
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
echo Testing errorhandler daemon &&\
echo setting volume config for invalid domain &&\
redis-cli set "worker:volume:config:${DOMAIN}" '{"hostname":"invalid.domain","zone":"EU"}' &&\
echo Starting errorhandled daemon &&\
docker run -d --name errorhandler --rm \
    -v "${HOME}/.kube/config:/root/.kube/config" \
    -v "${HOME}/.minikube:${HOME}/.minikube" \
    -e CWM_API_URL \
    -e CWM_ZONE \
    -e PACKAGES_READER_GITHUB_USER \
    -e PACKAGES_READER_GITHUB_TOKEN \
    -e REDIS_HOST \
    -e DEPLOYER_WAIT_DEPLOYMENT_READY_MAX_SECONDS \
    -e ERRORHANDLER_WAIT_DEPLOYMENT_READY_MAX_SECONDS \
    cwm_worker_operator errorhandler start &&\
echo Waiting for invalid domain to be available &&\
tests/wait_for.sh "
  [ \"\$(redis-cli --raw exists \"worker:available:${DOMAIN}\")\" == \"1\" ] &&\
  [ \"\$(redis-cli --raw get \"worker:ingress:hostname:${DOMAIN}\")\" == \"minio.${NAMESPACE}.svc.cluster.local\" ]
" "30" "waited too long for domain to be available" &&\
echo docker tests completed successfully &&\
docker rm -f errorhandler &&\
docker rm -f deployer &&\
docker rm -f redis &&\
exit 0
