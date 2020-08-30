#!/usr/bin/env bash

NAMESPACE="${1}"
echo Clearing namespace "${NAMESPACE}"
kubectl delete ns "${NAMESPACE}"
echo Waiting for namespace to be cleared...
while kubectl get ns "${NAMESPACE}"; do sleep 1; done
echo Namespace cleared
exit 0
