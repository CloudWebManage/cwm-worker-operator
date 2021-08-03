import importlib

import click


@click.group(context_settings={'max_content_width': 200})
def main():
    pass


def extra_commands_callback_decorator(callback):

    def _callback(*args, **kwargs):
        exit(0 if callback(*args, **kwargs) else 1)

    return _callback


for daemon in [
    {'name': 'initializer'},
    {'name': 'deployer', 'extra_commands': {
        'deploy_worker': {'callback_method': 'deploy_worker', 'params': [
            click.Option(['--worker-id']),
            click.Option(['--debug'], is_flag=True),
            click.Option(['--dry-run'], is_flag=True),
        ]}
    }},
    {'name': 'waiter'},
    {'name': 'deleter', 'extra_commands': {
        'delete': {'callback_method': 'delete', 'params': [
            click.Option(['--worker-id']),
            click.Option(['--hostname']),
            click.Option(['--deployment-timeout-string']),
            click.Option(['--with-metrics'], is_flag=True)
        ]}
    }},
    {'name': 'updater'},
    {'name': 'metrics-updater'},
    {'name': 'web-ui', 'with_once': False},
    {'name': 'disk-usage-updater'},
    {'name': 'alerter'},
    {'name': 'cleaner'},
    {'name': 'nodes-checker'},
    {'name': 'clear-cacher'},
]:
    main.add_command(click.Group(
        name=daemon['name'],
        commands={
            'start_daemon': click.Command(
                name='start_daemon',
                callback=importlib.import_module('cwm_worker_operator.{}'.format(daemon['name'].replace('-', '_'))).start_daemon,
                params=[
                    *([click.Option(['--once'], is_flag=True)] if daemon.get('with_once') != False else [])
                ]
            ),
            **{
                extra_command_name: click.Command(
                    name=extra_command_name,
                    callback=extra_commands_callback_decorator(getattr(importlib.import_module('cwm_worker_operator.{}'.format(daemon['name'].replace('-', '_'))), extra_command['callback_method'])),
                    params=extra_command['params']
                ) for extra_command_name, extra_command in daemon.get('extra_commands', {}).items()
            }
        }
    ))


@main.command()
@click.argument('QUERY_PARAM')
@click.argument('QUERY_VALUE')
def cwm_api_volume_config_api_call(query_param, query_value):
    import json
    from cwm_worker_operator.cwm_api_manager import CwmApiManager
    print(json.dumps(CwmApiManager().volume_config_api_call(query_param, query_value)))


@main.command()
@click.option('--force-update', is_flag=True)
@click.option('--hostname')
@click.option('--worker-id')
def get_cwm_api_volume_config(force_update=False, hostname=None, worker_id=None):
    from cwm_worker_operator import domains_config
    print(domains_config.DomainsConfig().get_cwm_api_volume_config(force_update=force_update, hostname=hostname, worker_id=worker_id))