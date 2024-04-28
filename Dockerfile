# Pulled Apr 28, 2024
FROM python:3.8-alpine@sha256:166faf3661e2b715e122d8203ce65a4e0f55e1bee11d8f10dc4751a2cecf5b9c
RUN apk update && apk add --no-cache git curl nfs-utils libffi-dev build-base librdkafka-dev
RUN curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" &&\
    chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl &&\
    kubectl version --client &&\
    curl -Ls https://get.helm.sh/helm-v3.2.4-linux-amd64.tar.gz -ohelm.tar.gz &&\
    tar -xzvf helm.tar.gz && mv linux-amd64/helm /usr/local/bin/helm &&\
    chmod +x /usr/local/bin/helm &&\
    rm -rf linux-amd64 && rm helm.tar.gz &&\
    helm version
RUN pip install --upgrade pip
RUN mkdir -p /usr/local/src/cwm-worker-operator
WORKDIR /usr/local/src/cwm-worker-operator
COPY requirements.txt requirements-cwm-worker-deployment.txt ./
RUN pip install -r requirements.txt
COPY setup.py .
COPY cwm_worker_operator ./cwm_worker_operator
RUN pip install -e .
ENV PYTHONUNBUFFERED=no
ENTRYPOINT ["cwm_worker_operator"]
