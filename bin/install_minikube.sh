#!/usr/bin/env bash

curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 &&\
chmod +x minikube && mv minikube /usr/local/bin/minikube &&\
minikube version
