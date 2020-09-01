#!/usr/bin/env bash

cwm_worker_deployment delete example007--com minio --delete-namespace >/dev/null 2>&1
cwm_worker_deployment delete differentvolume1--domain minio --delete-namespace >/dev/null 2>&1
cwm_worker_deployment delete differentvolume2--domain minio --delete-namespace >/dev/null 2>&1
cwm_worker_deployment delete timeoutdeploy--domain minio --delete-namespace >/dev/null 2>&1
cwm_worker_deployment delete invalid--domain minio --delete-namespace >/dev/null 2>&1
sleep 5
exit 0
