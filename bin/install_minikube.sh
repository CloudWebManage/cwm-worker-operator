#!/usr/bin/env bash

cd `mktemp -d` &&\
curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 &&\
chmod +x minikube && mv minikube /usr/local/bin/minikube
