from cwm_worker_operator import disk_usage_updater

from .mocks.metrics import MockDiskUsageUpdaterMetrics


def test_disk_usage_updater(domains_config):
    disk_usage_updater_metrics = MockDiskUsageUpdaterMetrics()
    cmds = []

    def subprocess_getstatusoutput(cmd):
        cmds.append(cmd)
        if cmd.startswith('ls '):
            return 0, 'foo bar baz'
        elif cmd.startswith('du '):
            return 0, '123\tfoo'
        else:
            return 0, ''

    disk_usage_updater.run_single_iteration(domains_config, disk_usage_updater_metrics, subprocess_getstatusoutput)
    assert cmds == [
        'umount -f /tmp/dum; mkdir -p /tmp/dum; mount -t nfs4 cwm-nfs:/ganesha-ceph/eu-vobjstore001 /tmp/dum',
        'ls /tmp/dum',
        'du -s /tmp/dum/foo',
        'du -s /tmp/dum/bar',
        'du -s /tmp/dum/baz',
    ]
    with domains_config.get_internal_redis() as r:
        for namespace_name in ['foo', 'bar', 'baz']:
            assert 125952 == 123 * 1024
            assert r.get('worker:total-used-bytes:{}'.format(namespace_name)) == b'125952'
