#!/usr/bin/env bash

DOMAIN="${1}"

[ "$(redis-cli --raw exists "worker:available:${DOMAIN}")" == "0" ] &&\
[ "$(redis-cli --raw exists "worker:error:${DOMAIN}")" == "1" ] &&\
[ "$(redis-cli --raw exists "worker:initialize:${DOMAIN}")" == "0" ]
