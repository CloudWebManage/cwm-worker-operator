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

tests/clear_deployments.sh &&\
tests/redis_clear.sh "${VALID_DOMAIN}" &&\
tests/redis_clear.sh "${MISSING_DOMAIN1}" &&\
tests/redis_clear.sh "${MISSING_DOMAIN2}" &&\
tests/redis_clear.sh "${INVALID_ZONE_DOMAIN1}" &&\
tests/redis_clear.sh "${INVALID_ZONE_DOMAIN2}" &&\
tests/redis_clear.sh "${DIFFERENT_VOLUME_CONFIG_DOMAIN1}" &&\
tests/redis_clear.sh "${DIFFERENT_VOLUME_CONFIG_DOMAIN2}" &&\
tests/redis_clear.sh "${FAIL_TO_DEPLOY_DOMAIN}" &&\
tests/redis_clear.sh "${TIMEOUT_DEPLOY_DOMAIN}" &&\
cwm_worker_operator errorhandler start --once >/dev/null &&\
sleep 2 &&\
redis-cli set "worker:error:${VALID_DOMAIN}" "" &&\
redis-cli set "worker:error:${MISSING_DOMAIN1}" "" &&\
redis-cli set "worker:error:${MISSING_DOMAIN2}" "" &&\
redis-cli set "worker:error:${INVALID_ZONE_DOMAIN1}" "" &&\
redis-cli set "worker:error:${INVALID_ZONE_DOMAIN2}" "" &&\
redis-cli set "worker:error:${DIFFERENT_VOLUME_CONFIG_DOMAIN1}" "" &&\
redis-cli set "worker:error:${DIFFERENT_VOLUME_CONFIG_DOMAIN2}" "" &&\
redis-cli set "worker:error:${FAIL_TO_DEPLOY_DOMAIN}" "" &&\
redis-cli set "worker:error:${TIMEOUT_DEPLOY_DOMAIN}" "" &&\
redis-cli set "worker:volume:config:${INVALID_ZONE_DOMAIN1}" '{"hostname":"invalidzone1.domain","zone":"US"}' &&\
redis-cli set "worker:volume:config:${INVALID_ZONE_DOMAIN2}" '{"hostname":"invalidzone2.domain","zone":"IL"}' &&\
redis-cli set "worker:volume:config:${DIFFERENT_VOLUME_CONFIG_DOMAIN1}" '{"hostname":"differentvolume.domain","zone":"EU","foo":"bar"}' &&\
redis-cli set "worker:volume:config:${DIFFERENT_VOLUME_CONFIG_DOMAIN2}" '{"hostname":"differentvolume.domain","zone":"EU","baz":"bax"}' &&\
redis-cli set "worker:volume:config:${FAIL_TO_DEPLOY_DOMAIN}" '{"hostname":"failtodeploy.domain","zone":"EU","minio_extra_configs":{"httpResources":"---invalid---"}}' &&\
redis-cli set "worker:volume:config:${TIMEOUT_DEPLOY_DOMAIN}" '{"hostname":"timeoutdeploy.domain","zone":"EU","certificate_pem":"invalid","certificate_key":"invalid","protocol":"https"}' &&\
cwm_worker_operator errorhandler start --once &&\
tail -1 .metrics.errorhandler | grep '"domain is available": 2' &&\
tail -1 .metrics.errorhandler | grep '"error: FAILED_TO_GET_VOLUME_CONFIG": 2' >/dev/null &&\
tail -1 .metrics.errorhandler | grep '"error: INVALID_VOLUME_ZONE": 2' >/dev/null &&\
tail -1 .metrics.errorhandler | grep '"error: DIFFERENT_VOLUME_CONFIGS": 1' >/dev/null &&\
tail -1 .metrics.errorhandler | grep '"error: FAILED_TO_DEPLOY": 1' >/dev/null &&\
tail -1 .metrics.errorhandler | grep '"error: TIMEOUT_WAITING_FOR_DEPLOYMENT": 1' >/dev/null &&\
tests/assert_valid_domain.sh "${VALID_DOMAIN}" "example007--com" "EU" &&\
tests/assert_missing_configuration_domain.sh "${MISSING_DOMAIN1}" &&\
tests/assert_missing_configuration_domain.sh "${MISSING_DOMAIN2}" &&\
tests/assert_error_domain.sh "${INVALID_ZONE_DOMAIN1}" &&\
tests/assert_error_domain.sh "${INVALID_ZONE_DOMAIN2}" &&\
tests/assert_error_domain.sh "${FAIL_TO_DEPLOY_DOMAIN}" &&\
tests/assert_error_domain.sh "${TIMEOUT_DEPLOY_DOMAIN}" &&\
[ "$(redis-cli --raw get "worker:error_attempt_number:${INVALID_ZONE_DOMAIN2}")" == "2" ]
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
