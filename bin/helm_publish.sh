#!/usr/bin/env bash

uci git checkout \
  --github-repo-name CloudWebManage/cwm-worker-helm \
  --branch-name master \
  --ssh-key "${CWM_WORKER_HELM_DEPLOY_KEY}" \
  --path cwm-worker-helm \
  --config-user-name cwm-worker-operator-ci &&\
mkdir -p cwm-worker-helm/cwm-worker-operator &&\
helm package ./helm --version "0.0.0-$(date +%Y%m%dT%H%M%S)" --destination ./cwm-worker-helm/cwm-worker-operator &&\
helm repo index --url "https://raw.githubusercontent.com/CloudWebManage/cwm-worker-helm/master/cwm-worker-operator/" ./cwm-worker-helm/cwm-worker-operator &&\
cd cwm-worker-helm &&\
git add cwm-worker-operator &&\
git commit -m "automatic update of cwm-worker-operator" &&\
git push origin master &&\
cd ..
