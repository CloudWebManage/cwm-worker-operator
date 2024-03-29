"""
Collects disk usage data for workers
"""
import json
import traceback
import subprocess

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig


def run_single_iteration(domains_config: DomainsConfig, metrics, subprocess_getstatusoutput, **_):
    disk_usage_updater_metrics = metrics
    ret, out = subprocess_getstatusoutput('umount -f /tmp/dum; mkdir -p /tmp/dum; mount -t nfs4 {}:{} /tmp/dum'.format(
        config.DISK_USAGE_UPDATER_NFS_SERVER, config.DISK_USAGE_UPDATER_NFS_ROOT_PATH))
    assert ret == 0, out
    ret, out = subprocess_getstatusoutput('ls /tmp/dum')
    assert ret == 0, out
    worker_ids_failed_validations = {}
    for namespace_name in out.split():
        namespace_name = namespace_name.strip()
        if namespace_name and namespace_name not in ['check_node_nas_health']:
            if common.is_worker_namespace(namespace_name):
                start_time = common.now()
                worker_id = common.get_worker_id_from_namespace_name(namespace_name)
                try:
                    worker_id_validation = domains_config.validate_worker_id(worker_id)
                    if worker_id_validation is True:
                        ret, out = subprocess_getstatusoutput('du -s /tmp/dum/{}'.format(namespace_name))
                        if ret != 0:
                            logs.debug_info("encountered errors when running du: {}".format(out), worker_id=worker_id, start_time=start_time)
                            out = out.splitlines()[-1]
                        total_used_bytes = int(out.split()[0]) * 1024
                        domains_config.set_worker_total_used_bytes(worker_id, total_used_bytes)
                        disk_usage_updater_metrics.disk_usage_update(worker_id, start_time)
                    else:
                        worker_ids_failed_validations[namespace_name] = worker_id_validation
                except Exception as e:
                    logs.debug_info("exception: {}".format(e), worker_id=worker_id, start_time=start_time)
                    if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                        traceback.print_exc()
                    disk_usage_updater_metrics.exception(worker_id, start_time)
            else:
                worker_ids_failed_validations[namespace_name] = 'not worker namespace'
    if len(worker_ids_failed_validations) > 0:
        logs.alert(
            domains_config,
            f'disk_usage_updater found namespaces which failed worker id validation: {json.dumps(worker_ids_failed_validations)}'
        )

def start_daemon(once=False, with_prometheus=True, disk_usage_updater_metrics=None, domains_config=None, subprocess_getstatusoutput=None):
    if subprocess_getstatusoutput is None:
        subprocess_getstatusoutput = subprocess.getstatusoutput
    Daemon(
        name='disk_usage_updater',
        sleep_time_between_iterations_seconds=config.DISK_USAGE_UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.DiskUsageUpdaterMetrics,
        domains_config=domains_config,
        metrics=disk_usage_updater_metrics,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_DISK_USAGE_UPDATER,
        run_single_iteration_extra_kwargs={'subprocess_getstatusoutput': subprocess_getstatusoutput}
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
