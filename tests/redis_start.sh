#!/usr/bin/env bash

echo stsarting Redis
docker rm -f redis
! docker run -d --rm --name redis -p 6379:6379 redis && echo failed to start Redis && exit 1
while ! redis-cli ping; do sleep 1; done
echo Redis started successfully
exit 0
