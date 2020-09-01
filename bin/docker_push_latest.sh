#!/usr/bin/env bash

BUILD_IMAGE=cwm_worker_operator
PUSH_IMAGE=docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest

docker tag "${BUILD_IMAGE}" "${PUSH_IMAGE}" &&\
docker push "${PUSH_IMAGE}"
