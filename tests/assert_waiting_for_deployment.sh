#!/usr/bin/env bash

DOMAIN="${1}"

[ "$(redis-cli --raw exists "worker:opstatus:waiting_for_deployment:${DOMAIN}")" == "1" ]
