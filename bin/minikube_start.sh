#!/usr/bin/env bash

minikube start --driver=docker --kubernetes-version=$1 --network-plugin=cni --cni=calico &
