import sys
import importlib
import subprocess

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
            click.Option(['--extra-minio-extra-configs']),
            click.Option(['--debug'], is_flag=True),
            click.Option(['--dry-run'], is_flag=True),
        ], 'help': 'Deploy a single worker, used by deployer to run async operations'}
    }},
    {'name': 'waiter', 'extra_commands': {
        'check_deployment_complete': {'callback_method': 'check_deployment_complete', 'params': [
            click.Option(['--worker-id']),
        ], 'help': 'Wait for a single worker, used by waiter to run async operations'}
    }},
    {'name': 'deleter', 'extra_commands': {
        'delete': {'callback_method': 'delete', 'params': [
            click.Option(['--worker-id']),
            click.Option(['--hostname']),
            click.Option(['--deployment-timeout-string']),
            click.Option(['--with-metrics'], is_flag=True),
            click.Option(['--force-now'], is_flag=True),
        ], 'help': 'Manually delete a worker for debugging'}
    }},
    {'name': 'updater', 'extra_commands': {
        'update': {'callback_method': 'update', 'params': [
            click.Option(['--namespace-name']),
            click.Option(['--last-updated']),
            click.Option(['--status']),
            click.Option(['--revision']),
            click.Option(['--worker-id']),
            click.Option(['--instance-update']),
            click.Option(['--start-time']),
        ], 'help': 'Update a single worker, used by updater to run async operations'}
    }},
    {'name': 'metrics-updater'},
    {'name': 'web-ui', 'with_once': False},
    {'name': 'disk-usage-updater'},
    {'name': 'alerter'},
    {'name': 'cleaner'},
    {'name': 'nodes-checker'},
    {'name': 'clear-cacher'},
    {'name': 'nas-checker'},
    {'name': 'redis-cleaner'},
    {'name': 'workers-checker', 'extra_commands': {
        'process_worker': {'callback_method': 'process_worker_cli', 'params': [
            click.Option(['--worker-id']),
        ], 'help': 'Check and update a single worker, used by workers-checker to run async operations'}
    }},
    {'name': 'throttler'},
    {
        'name': 'kafka-streamer',
        'extra_params': [
            click.Option(['--topic']),
            click.Option(['--no-kafka-commit'], is_flag=True),
            click.Option(['--no-kafka-delete'], is_flag=True),
        ]
    },
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
                        *([click.Option(['--once'], is_flag=True)] if daemon.get('with_once') != False else []),
                        *(daemon['extra_params'] if 'extra_params' in daemon else []),
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
@click.option('--api-version')
def cwm_api_volume_config_api_call(**kwargs):
    """Make a low-level API call to get cwm instance volume configuration

    Supported QUERY_PARAM values: id / hostname
    """
    import json
    from cwm_worker_operator.cwm_api_manager import CwmApiManager
    print(json.dumps(CwmApiManager().volume_config_api_call(**kwargs)))


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


@main.command(short_help="Start Minio Auth Server for development")
def start_minio_auth_server_devel():
    """
    Start Minio Auth Server for development
    """
    import uvicorn
    uvicorn.run('cwm_worker_operator.minio_auth_plugin.app:app', host='0.0.0.0', port=5000, reload=True)


@main.command(short_help="Start consecutive daemon run once commands")
@click.argument('DAEMON_NAME', nargs=-1)
def multi_run_once(daemon_name):
    for name in daemon_name:
        print(f'Running {name} --run-once')
        subprocess.check_call([
            'cwm-worker-operator', name, 'start_daemon', '--once'
        ])


if __name__ == '__main__':
    main()
