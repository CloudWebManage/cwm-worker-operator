#!/usr/bin/env bash

CACHE_FROM_IMAGE=docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest
BUILD_IMAGE=cwm_worker_operator

docker pull "${CACHE_FROM_IMAGE}" &&\
docker build --cache-from "${CACHE_FROM_IMAGE}" -t "${BUILD_IMAGE}" .
