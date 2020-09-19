#!/usr/bin/env bash

DOMAIN="${1}"
ERROR_ATTEMPT="${2}"

[ "$(redis-cli --raw exists "worker:error:${DOMAIN}")" == "0" ] &&\
[ "$(redis-cli --raw get "worker:error_attempt_number:${DOMAIN}" | tee /dev/stderr)" == "${ERROR_ATTEMPT}" ]
