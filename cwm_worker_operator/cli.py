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
    {'name': 'deployer'},
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
