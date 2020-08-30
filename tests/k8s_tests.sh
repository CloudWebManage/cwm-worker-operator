#!/usr/bin/env bash

echo starting k8s tests &&\
echo testing deployer - valid domain &&\
DOMAIN=example007.com &&\
NAMESPACE=example007--com &&\
tests/redis_clear.sh "${DOMAIN}" &&\
tests/namespace_clear.sh "${NAMESPACE}" &&\
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
" "30" "waited too long for domain to be errored"
if [ "$?" != "0" ]; then
  kubectl logs deployment/cwm-worker-operator -c deployer
  exit 1
fi

echo Testing errorhandler daemon &&\
echo setting volume config for invalid domain &&\
redis-cli set "worker:volume:config:${DOMAIN}" '{"hostname":"invalid.domain","zone":"EU"}' &&\
echo Waiting for invalid domain to be available &&\
tests/wait_for.sh "
  [ \"\$(redis-cli --raw exists \"worker:available:${DOMAIN}\")\" == \"1\" ] &&\
  [ \"\$(redis-cli --raw get \"worker:ingress:hostname:${DOMAIN}\")\" == \"minio.${NAMESPACE}.svc.cluster.local\" ]
" "30" "waited too long for domain to be available"
if [ "$?" != "0" ]; then
  kubectl logs deployment/cwm-worker-operator -c errorhandler
  exit 1
fi

echo k8s tests completed successfully &&\
exit 0
