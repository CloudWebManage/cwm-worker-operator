#!/usr/bin/env bash

docker pull redis@sha256:33ca074e6019b451235735772a9c3e7216f014aae8eb0580d7e94834fe23efb3 &&\
docker run -d --rm --name redis -p 6379:6379 redis &&\
which redis-cli &&\
while ! redis-cli ping; do sleep 1; done
