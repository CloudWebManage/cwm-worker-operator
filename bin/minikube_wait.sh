#!/usr/bin/env bash

tests/wait_for.sh "minikube status" "240" "waited too long for minikube to start" &&\
kubectl get nodes
