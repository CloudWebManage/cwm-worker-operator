from cwm_worker_operator import disk_usage_updater, common
from cwm_worker_operator.domains_config import WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID

from .mocks.metrics import MockDiskUsageUpdaterMetrics


def test_disk_usage_updater(domains_config):
    disk_usage_updater_metrics = MockDiskUsageUpdaterMetrics()

    worker_id_1 = 'worker1'
    worker_id_2 = 'worker2'
    worker_id_3 = 'worker3'
    namespace_name_1 = common.get_namespace_name_from_worker_id(worker_id_1)
    namespace_name_2 = common.get_namespace_name_from_worker_id(worker_id_2)
    namespace_name_3 = common.get_namespace_name_from_worker_id(worker_id_3)
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id_1)] = {'instanceId': worker_id_1}
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id_2)] = {'instanceId': worker_id_2}
    domains_config._cwm_api_volume_configs['id:{}'.format(worker_id_3)] = {'instanceId': worker_id_3}

    namespace_name_invalid = 'invalid'

    cmds = []

    def subprocess_getstatusoutput(cmd):
        cmds.append(cmd)
        if cmd.startswith('ls '):
            return 0, f'{namespace_name_1} {namespace_name_2} {namespace_name_3} {namespace_name_invalid}'
        elif cmd.startswith('du '):
            return 0, '123\tfoo'
        else:
            return 0, ''

    disk_usage_updater.run_single_iteration(domains_config, disk_usage_updater_metrics, subprocess_getstatusoutput)
    assert cmds == [
        'umount -f /tmp/dum; mkdir -p /tmp/dum; mount -t nfs4 cwm-nfs:/ganesha-ceph/eu-vobjstore001 /tmp/dum',
        'ls /tmp/dum',
        f'du -s /tmp/dum/{namespace_name_1}',
        f'du -s /tmp/dum/{namespace_name_2}',
        f'du -s /tmp/dum/{namespace_name_3}',
    ]
    for namespace_name in [namespace_name_1, namespace_name_2, namespace_name_3]:
        assert 125952 == 123 * 1024
        worker_id = common.get_worker_id_from_namespace_name(namespace_name)
        assert domains_config.get_worker_total_used_bytes(worker_id) == 125952
    alerts = []
    while True:
        alert = domains_config.alerts_pop()
        if alert:
            alerts.append(alert)
        else:
            break
    assert len(alerts) == 1
    worker_ids_failed_validations = {namespace_name_invalid: WORKER_ID_VALIDATION_MISSING_VOLUME_CONFIG_ID}
    assert alerts[0] == {
        'type': 'cwm-worker-operator-logs',
        'msg': f'disk_usage_updater found namespaces which failed worker id validation: {worker_ids_failed_validations}',
        'kwargs': {}
    }