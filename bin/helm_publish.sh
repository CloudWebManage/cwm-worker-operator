#!/usr/bin/env bash

echo "${CWM_WORKER_HELM_DEPLOY_KEY}" > cwm_worker_helm_deploy_key &&\
chmod 400 cwm_worker_helm_deploy_key &&\
export GIT_SSH_COMMAND="ssh -i $(pwd)/cwm_worker_helm_deploy_key -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no" &&\
git clone git@github.com:CloudWebManage/cwm-worker-helm.git &&\
git config --global user.name "cwm-worker-operator CI" &&\
git config --global user.email "cwm-worker-operator-ci@localhost" &&\
mkdir -p cwm-worker-helm/cwm-worker-operator &&\
helm package ./helm --version "0.0.0-$(date +%Y%m%dT%H%M%S)" --destination ./cwm-worker-helm/cwm-worker-operator &&\
helm repo index --url "https://raw.githubusercontent.com/CloudWebManage/cwm-worker-helm/master/cwm-worker-operator/" ./cwm-worker-helm/cwm-worker-operator &&\
cd cwm-worker-helm &&\
git add cwm-worker-operator &&\
git commit -m "automatic update of cwm-worker-operator" &&\
git push origin master &&\
cd ..
