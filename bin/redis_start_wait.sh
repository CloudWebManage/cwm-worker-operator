#!/usr/bin/env bash

docker run -d --rm --name redis -p 6379:6379 redis &&\
which redis-cli &&\
while ! redis-cli ping; do sleep 1; done
