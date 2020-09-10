#!/usr/bin/env bash

VALID_DOMAIN=example007.com
MISSING_DOMAIN1=missing1.domain
MISSING_DOMAIN2=missing2.domain
INVALID_ZONE_DOMAIN1=invalidzone1.domain
INVALID_ZONE_DOMAIN2=invalidzone2.domain
DIFFERENT_VOLUME_CONFIG_DOMAIN1=differentvolume1.domain
DIFFERENT_VOLUME_CONFIG_DOMAIN2=differentvolume2.domain
FAIL_TO_DEPLOY_DOMAIN=failtodeploy.domain
TIMEOUT_DEPLOY_DOMAIN=timeoutdeploy.domain

for DOMAIN in "${VALID_DOMAIN}" "${MISSING_DOMAIN1}" "${MISSING_DOMAIN2}" "${INVALID_ZONE_DOMAIN1}" "${INVALID_ZONE_DOMAIN2}"  \
              "${DIFFERENT_VOLUME_CONFIG_DOMAIN1}" "${DIFFERENT_VOLUME_CONFIG_DOMAIN2}" "${FAIL_TO_DEPLOY_DOMAIN}" "${TIMEOUT_DEPLOY_DOMAIN}"
do
  if ! DELETER_OUTPUT="$( (cwm_worker_operator deleter delete "${DOMAIN}") 2>&1 )"; then
      echo "${DELETER_OUTPUT}"
      echo failed to delete domain "${DOMAIN}"
      exit 1
  fi
done &&\
cwm_worker_operator deployer start --once >/dev/null &&\
sleep 2 &&\
redis-cli set "worker:initialize:${VALID_DOMAIN}" "" &&\
redis-cli set "worker:initialize:${MISSING_DOMAIN1}" "" &&\
redis-cli set "worker:initialize:${MISSING_DOMAIN2}" "" &&\
redis-cli set "worker:initialize:${INVALID_ZONE_DOMAIN1}" "" &&\
redis-cli set "worker:initialize:${INVALID_ZONE_DOMAIN2}" "" &&\
redis-cli set "worker:initialize:${DIFFERENT_VOLUME_CONFIG_DOMAIN1}" "" &&\
redis-cli set "worker:initialize:${DIFFERENT_VOLUME_CONFIG_DOMAIN2}" "" &&\
redis-cli set "worker:initialize:${FAIL_TO_DEPLOY_DOMAIN}" "" &&\
redis-cli set "worker:initialize:${TIMEOUT_DEPLOY_DOMAIN}" "" &&\
redis-cli set "worker:volume:config:${INVALID_ZONE_DOMAIN1}" '{"hostname":"invalidzone1.domain","zone":"US"}' &&\
redis-cli set "worker:volume:config:${INVALID_ZONE_DOMAIN2}" '{"hostname":"invalidzone2.domain","zone":"IL"}' &&\
redis-cli set "worker:volume:config:${DIFFERENT_VOLUME_CONFIG_DOMAIN1}" '{"hostname":"differentvolume.domain","zone":"EU","foo":"bar"}' &&\
redis-cli set "worker:volume:config:${DIFFERENT_VOLUME_CONFIG_DOMAIN2}" '{"hostname":"differentvolume.domain","zone":"EU","baz":"bax"}' &&\
redis-cli set "worker:volume:config:${FAIL_TO_DEPLOY_DOMAIN}" '{"hostname":"failtodeploy.domain","zone":"EU","minio_extra_configs":{"httpResources":"---invalid---"}}' &&\
redis-cli set "worker:volume:config:${TIMEOUT_DEPLOY_DOMAIN}" '{"hostname":"timeoutdeploy.domain","zone":"EU","certificate_pem":"invalid","certificate_key":"invalid","protocol":"https"}' &&\
cwm_worker_operator deployer start --once &&\
tail -1 .metrics.deployer | grep '"domain is available": 2' &&\
tail -1 .metrics.deployer | grep '"error: FAILED_TO_GET_VOLUME_CONFIG": 2' >/dev/null &&\
tail -1 .metrics.deployer | grep '"error: INVALID_VOLUME_ZONE": 2' >/dev/null &&\
tail -1 .metrics.deployer | grep '"error: DIFFERENT_VOLUME_CONFIGS": 1' >/dev/null &&\
tail -1 .metrics.deployer | grep '"error: FAILED_TO_DEPLOY": 1' >/dev/null &&\
tail -1 .metrics.deployer | grep '"error: TIMEOUT_WAITING_FOR_DEPLOYMENT": 1' >/dev/null &&\
tests/assert_valid_domain.sh "${VALID_DOMAIN}" "example007--com" "EU" &&\
tests/assert_missing_configuration_domain.sh "${MISSING_DOMAIN1}" &&\
tests/assert_missing_configuration_domain.sh "${MISSING_DOMAIN2}" &&\
tests/assert_error_domain.sh "${INVALID_ZONE_DOMAIN1}" &&\
tests/assert_error_domain.sh "${INVALID_ZONE_DOMAIN2}" &&\
tests/assert_error_domain.sh "${FAIL_TO_DEPLOY_DOMAIN}" &&\
tests/assert_error_domain.sh "${TIMEOUT_DEPLOY_DOMAIN}"
if [ "$?" == "0" ]; then
  exit 0
else
  kubectl get ns
  for NS in differentvolume--domain example007--com failtodeploy--domain timeoutdeploy--domain; do
    echo "--- $NS ---"
    kubectl -n $NS get deployment minio
    POD="$(kubectl -n $NS get pods | tee /dev/stderr | grep minio | cut -d" " -f1)"
    kubectl -n $NS describe pod $POD
    for C in http https; do
      echo "- container: $C -"
      kubectl -n $NS logs $POD -c $C
    done
  done
  exit 1
fi