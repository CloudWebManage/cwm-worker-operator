#!/usr/bin/env bash

DOMAIN="${1}"

for KEY in "worker:available:${DOMAIN}" \
           "worker:ingress:hostname:${DOMAIN}" \
           "worker:error:${DOMAIN}" \
           "worker:initialize:${DOMAIN}" \
           "worker:error_attempt_number:${DOMAIN}" \
           "worker:volume:config:${DOMAIN}"
do
  redis-cli del "${KEY}" >/dev/null
done
