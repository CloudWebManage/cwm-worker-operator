import json
import datetime

from cwm_worker_operator import workers_checker, common


def test_invalid_namespace_with_no_resources(domains_config, deployments_manager):
    worker_id = 'worker1'
    namespace = common.get_namespace_name_from_worker_id(worker_id)
    updated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    deployments_manager.all_releases = [
        {
            "namespace": namespace,
            "updated": updated_at,
            "status": "deployed",
            "app_version": "",
            "revision": 1
        }
    ]
    workers_checker.run_single_iteration(domains_config, deployments_manager)
    health_json = domains_config.keys.worker_health.get(worker_id)
    assert json.loads(health_json) == {
        "namespace": "Inactive",
        "pods": {
            "minio-server": {
                "status": "Not Found",
                "running": 0
            },
            "minio-nginx": {
                "status": "Not Found",
                "running": 0
            },
            "minio-logger": {
                "status": "Not Found",
                "running": 0
            },
            "minio-external-scaler": {
                "status": "Not Found",
                "running": 0
            }
        }
    }
