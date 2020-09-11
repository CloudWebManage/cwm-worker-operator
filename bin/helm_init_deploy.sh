#!/usr/bin/env bash

docker rm -f redis
export DEBUG=

HELMARGS="--set cwm_api_url=${CWM_API_URL},packages_reader_github_user=${PACKAGES_READER_GITHUB_USER},packages_reader_github_token=${PACKAGES_READER_GITHUB_TOKEN}" &&\
if ! kubectl get secret github; then
  echo '{"auths":{"docker.pkg.github.com":{"auth":"'"$(echo -n "${PACKAGES_READER_GITHUB_USER}:${PACKAGES_READER_GITHUB_TOKEN}" | base64 -w0)"'"}}}' | kubectl create secret generic github --type=kubernetes.io/dockerconfigjson --from-file=.dockerconfigjson=/dev/stdin
fi &&\
sed -i "s/appVersion: latest/appVersion: ${GITHUB_SHA}/g" helm/Chart.yaml &&\
helm upgrade --install cwm-worker-operator ./helm $HELMARGS &&\
if ! tests/wait_for.sh "
  kubectl get pods | grep cwm-worker-operator-redis | grep 'Running' | grep '1/1' &&\
  kubectl get pods | grep cwm-worker-operator | grep -v cwm-worker-operator-redis | grep 'Running' | grep '2/2' &&\
  kubectl exec deployment/cwm-worker-operator -c deployer -- tail -1 .metrics.deployer &&\
  kubectl exec deployment/cwm-worker-operator -c errorhandler -- tail -1 .metrics.errorhandler
  " "120" "waited too long for cwm-worker-operator to be deployed"
then
  kubectl get pods
  kubectl describe pod cwm-worker-operator
  kubectl logs deployment/cwm-worker-operator -c deployer | tail
  kubectl logs deployment/cwm-worker-operator -c errorhandler | tail
  exit 1
else
  sleep 5
  kubectl port-forward service/cwm-worker-operator-redis 6379 &
  exit 0
fi
