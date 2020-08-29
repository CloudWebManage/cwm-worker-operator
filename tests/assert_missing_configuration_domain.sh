#!/usr/bin/env bash

DOMAIN="${1}"

[ "$(redis-cli --raw exists "worker:available:${DOMAIN}")" == "0" ] &&\
[ "$(redis-cli --raw exists "worker:error:${DOMAIN}")" == "1" ] &&\
[ "$(redis-cli --raw exists "worker:initialize:${DOMAIN}")" == "0" ] &&\
redis-cli --raw get "worker:volume:config:${DOMAIN}" | grep '"__last_update": ' >/dev/null &&\
redis-cli --raw get "worker:volume:config:${DOMAIN}" | grep '"__error": ' >/dev/null
