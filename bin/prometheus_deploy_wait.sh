#!/usr/bin/env bash

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts &&\
helm repo update &&\
helm install prometheus prometheus-community/kube-prometheus-stack --values tests/kube-prometheus-stack.values.yaml &&\
uci util wait-for --timeout-seconds 300 --timeout-message "waited too long for prometheus" \
  '[ "$(kubectl get pods | grep prometheus | grep Running | wc -l)" == "4" ]'
