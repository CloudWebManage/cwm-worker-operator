#!/usr/bin/env bash

cd `mktemp -d` &&\
curl -Lo minikube.tar.gz https://github.com/kubernetes/minikube/releases/download/v1.21.0/minikube-linux-amd64.tar.gz &&\
tar -xzvf minikube.tar.gz && mv out/* /usr/local/bin/ &&\
mv /usr/local/bin/minikube{-linux-amd64,} &&\
chmod +x /usr/local/bin/minikube
