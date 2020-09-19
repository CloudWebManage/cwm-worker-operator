#!/usr/bin/env bash

DOMAIN="${1}"

[ "$(redis-cli --raw exists "worker:opstatus:ready_for_deployment:${DOMAIN}")" == "1" ]
