#!/usr/bin/env bash

for NAMESPACE in example007--com differentvolume1--domain differentvolume2--domain timeoutdeploy--domain invalid--domain; do
  cwm_worker_deployment delete $NAMESPACE minio --delete-namespace --timeout 1m0s
  while kubectl get ns $NAMESPACE; do sleep 1; done
done
exit 0
