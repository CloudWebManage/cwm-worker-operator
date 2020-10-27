import subprocess


def build_operator_docker_for_minikube():
    print('building docker image for minikube')
    returncode = subprocess.call("""
        eval $(minikube -p minikube docker-env) &&\
        docker pull docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest &&\
        docker build --cache-from docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest \
                     -t docker.pkg.github.com/cloudwebmanage/cwm-worker-operator/cwm_worker_operator:latest .
    """, shell=True)
    assert returncode == 0


def set_github_secret():
    returncode, _ = subprocess.getstatusoutput('kubectl get secret github')
    if returncode != 0:
        print("Setting github pull secret")
        returncode, output = subprocess.getstatusoutput(
            """echo '{"auths":{"docker.pkg.github.com":{"auth":"'"$(echo -n "${PACKAGES_READER_GITHUB_USER}:${PACKAGES_READER_GITHUB_TOKEN}" | base64 -w0)"'"}}}' | kubectl create secret generic github --type=kubernetes.io/dockerconfigjson --from-file=.dockerconfigjson=/dev/stdin""")
        assert returncode == 0, output
