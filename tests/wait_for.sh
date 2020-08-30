#!/usr/bin/env bash

WAIT_FOR_EVAL="${1}"
WAIT_SECONDS="${2}"
ERR_MSG="${3}"

ELAPSED_SECONDS=0
while ! eval "${WAIT_FOR_EVAL}"; do
  sleep 1; ELAPSED_SECONDS="$(expr $ELAPSED_SECONDS + 1)"
  [ "${ELAPSED_SECONDS}" == "${WAIT_SECONDS}" ] && echo "${ERR_MSG}" && exit 1
done
exit 0
