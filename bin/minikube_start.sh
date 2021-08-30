#!/usr/bin/env bash

minikube start --driver=docker --kubernetes-version=$1 &
