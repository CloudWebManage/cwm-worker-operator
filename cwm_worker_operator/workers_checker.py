"""
Check workers and update status in Redis
"""

import json
import subprocess

from cwm_worker_operator import config, common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


PODS = [ 'minio-server', 'minio-nginx', 'minio-logger', 'minio-external-scaler' ]


def get_running_pod_count(namespace, pod):
    cmd = f'kubectl get pods -n {namespace} -l app={pod} --field-selector status.phase=Running --no-headers 2>/dev/null | wc -l'
    ret, out = subprocess.getstatusoutput(cmd)
    assert ret == 0, out
    return int(out)


def get_pods(namespace):
    pods_with_count = {}
    for pod in PODS:
        running_pod_count = get_running_pod_count(namespace, pod)
        pods_with_count[pod] = {
            'status': 'Available' if running_pod_count > 0 else 'Not Found',
            'running': running_pod_count
        }
    return pods_with_count


def update_health_in_redis(domains_config, worker_id, health_json):
    domains_config.keys.worker_health.set(worker_id, health_json)


def run_single_iteration(domains_config: DomainsConfig, deployments_manager, **_):
    for release in deployments_manager.iterate_all_releases():
        namespace = release['namespace']
        worker_id = common.get_worker_id_from_namespace_name(namespace)
        is_ready = deployments_manager.is_ready(namespace, 'minio')
        pods = get_pods(namespace)
        health = {
            'namespace': 'Active' if is_ready else 'Inactive',
            'pods': pods
        }
        update_health_in_redis(domains_config, worker_id, json.dumps(health))


def start_daemon(once=False, domains_config=None, deployments_manager=None):
    Daemon(
        name="workers_checker",
        sleep_time_between_iterations_seconds=config.WORKERS_CHECKER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=False
    )
