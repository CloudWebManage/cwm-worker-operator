import sys
import importlib
import click


@click.group()
def main():
    pass


def extra_commands_callback_decorator(callback):

    def _callback(*args, **kwargs):
        exit(0 if callback(*args, **kwargs) else 1)

    return _callback


kubernetes_not_configured = False
for daemon in [
    {'name': 'initializer'},
    {'name': 'deployer', 'extra_commands': {
        'deploy_worker': {'callback_method': 'deploy_worker', 'params': [
            click.Option(['--worker-id']),
            click.Option(['--debug'], is_flag=True),
            click.Option(['--dry-run'], is_flag=True),
        ], 'help': 'Manually deploy a worker for debugging'}
    }},
    {'name': 'waiter'},
    {'name': 'deleter', 'extra_commands': {
        'delete': {'callback_method': 'delete', 'params': [
            click.Option(['--worker-id']),
            click.Option(['--hostname']),
            click.Option(['--deployment-timeout-string']),
            click.Option(['--with-metrics'], is_flag=True)
        ], 'help': 'Manually delete a worker for debugging'}
    }},
    {'name': 'updater'},
    {'name': 'metrics-updater'},
    {'name': 'web-ui', 'with_once': False},
    {'name': 'disk-usage-updater'},
    {'name': 'alerter'},
    {'name': 'cleaner'},
    {'name': 'nodes-checker'},
    {'name': 'clear-cacher'},
    {'name': 'nas-checker'},
    {'name': 'redis-cleaner'},
    {'name': 'workers-checker'},
]:
    try:
        daemon_module = importlib.import_module('cwm_worker_operator.{}'.format(daemon['name'].replace('-', '_')))
        main.add_command(click.Group(
            name=daemon['name'],
            help=daemon_module.__doc__,
            short_help=daemon_module.__doc__,
            commands={
                'start_daemon': click.Command(
                    name='start_daemon',
                    callback=daemon_module.start_daemon,
                    params=[
                        *([click.Option(['--once'], is_flag=True)] if daemon.get('with_once') != False else [])
                    ]
                ),
                **{
                    extra_command_name: click.Command(
                        name=extra_command_name,
                        callback=extra_commands_callback_decorator(getattr(importlib.import_module('cwm_worker_operator.{}'.format(daemon['name'].replace('-', '_'))), extra_command['callback_method'])),
                        params=extra_command['params'],
                        help=extra_command['help']
                    ) for extra_command_name, extra_command in daemon.get('extra_commands', {}).items()
                }
            }
        ))
    except Exception as e:
        if str(e) == 'Could not configure kubernetes python client':
            kubernetes_not_configured = True
        else:
            raise
if kubernetes_not_configured:
    print("WARNING! Kubernetes is not configured, some commands are not available", file=sys.stderr)


@main.command(short_help="Make a low-level API call to get cwm instance volume configuration")
@click.argument('QUERY_PARAM')
@click.argument('QUERY_VALUE')
def cwm_api_volume_config_api_call(query_param, query_value):
    """Make a low-level API call to get cwm instance volume configuration

    Supported QUERY_PARAM values: id / hostname
    """
    import json
    from cwm_worker_operator.cwm_api_manager import CwmApiManager
    print(json.dumps(CwmApiManager().volume_config_api_call(query_param, query_value)))


@main.command(short_help="Make an operator api call to get instance volume config from cache")
@click.option('--force-update', is_flag=True, help='Ignore the cache and force update from CWM api')
@click.option('--hostname')
@click.option('--worker-id')
def get_cwm_api_volume_config(force_update=False, hostname=None, worker_id=None):
    """
    Make an operator api call to get instance volume config from cache
    """
    from cwm_worker_operator import domains_config
    print(domains_config.DomainsConfig().get_cwm_api_volume_config(force_update=force_update, hostname=hostname, worker_id=worker_id))


@main.command(short_help="Make a low-level CWM api call to get cwm instance updates in the given time-range")
@click.option('--from-before-seconds')
@click.option('--from-datetime')
def get_cwm_updates(from_before_seconds, from_datetime):
    """
    Make a low-level CWM api call to get cwm instance updates in the given time-range
    """
    import datetime
    import json
    from cwm_worker_operator.cwm_api_manager import CwmApiManager
    from cwm_worker_operator import common
    if from_before_seconds:
        assert not from_datetime
        from_datetime = common.now() - datetime.timedelta(seconds=int(from_before_seconds))
    else:
        assert from_datetime
        from_datetime = common.strptime(from_datetime, '%Y-%m-%d %H:%M:%S')
    print('[')
    for update in CwmApiManager().get_cwm_updates(from_datetime):
        print('  ' + json.dumps({'worker_id': update['worker_id'], 'update_time': update['update_time'].strftime('%Y-%m-%d %H:%M:%S')}))
    print(']')


@main.command(short_help="Send aggregated metrics to CWM api for debugging")
@click.argument('WORKER_ID')
@click.argument('MINUTES_JSON')
def send_agg_metrics(worker_id, minutes_json):
    """
    Send aggregated metrics to CWM api for debugging

    \b
    Example minutes_json data ("t": "%Y%m%d%H%M%S"):
    [
        {
            "t": "20210825214533",
            "disk_usage_bytes": 100,
            "bytes_in": 200,
            "bytes_out": 300,
            "num_requests_in": 5,
            "num_requests_out": 10,
            "num_requests_misc": 15,
            "sum_cpu_seconds": 50,
            "ram_limit_bytes": 100
        }
    ]
    """
    import json
    from cwm_worker_operator.cwm_api_manager import CwmApiManager
    CwmApiManager().send_agg_metrics(worker_id, json.loads(minutes_json))
