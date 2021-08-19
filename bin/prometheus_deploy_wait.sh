#!/usr/bin/env bash

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts &&\
helm repo update &&\
helm install prometheus prometheus-community/kube-prometheus-stack --values tests/kube-prometheus-stack.values.yaml &&\
tests/wait_for.sh '[ "$(kubectl get pods | grep prometheus | grep Running | wc -l)" == "4" ]' 240 "waited too long for prometheus"
