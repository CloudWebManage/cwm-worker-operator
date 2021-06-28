#!/usr/bin/env bash

cd `mktemp -d` &&\
curl -LO "https://storage.googleapis.com/kubernetes-release/release/v1.19.0/bin/linux/amd64/kubectl" &&\
chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl
