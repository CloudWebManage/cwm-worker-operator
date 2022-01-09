"""
Initiates updates for workers, also sends aggregated metrics to CWM
"""
import datetime
import traceback
import subprocess

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import logs
from cwm_worker_operator import metrics_updater
from cwm_worker_operator.cwm_api_manager import CwmApiManager
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.multiprocessor import Multiprocessor


DATETIME_FORMAT = '%Y%m%dT%H%M%S%z'


def get_datetime_object(val):
    if isinstance(val, datetime.datetime):
        return val
    else:
        return datetime.datetime.strptime(val, DATETIME_FORMAT)


def get_datetime_string(dt: datetime.datetime):
    return dt.strftime(DATETIME_FORMAT)


def check_worker_force_delete_from_metrics(namespace_name, domains_config):
    last_action = domains_config.get_deployment_last_action(namespace_name)
    if last_action:
        return (common.now() - last_action).total_seconds() / 60 >= config.FORCE_DELETE_IF_NO_ACTION_FOR_MINUTES
    else:
        return True


def check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision,
                         instance_update, worker_id, start_time):
    try:
        if instance_update == 'delete':
            msg = "domain force delete (from cwm updates api)"
            logs.debug(msg, debug_verbosity=4, worker_id=worker_id, start_time=start_time)
            domains_config.set_worker_force_delete(worker_id, allow_cancel=False)
            if updater_metrics:
                updater_metrics.force_delete(worker_id, start_time)
        elif instance_update == 'update':
            msg = "domain force update (from cwm updates api)"
            logs.debug(msg, debug_verbosity=4, worker_id=worker_id, start_time=start_time)
            domains_config.set_worker_force_update(worker_id)
            if updater_metrics:
                updater_metrics.not_deployed_force_update(worker_id, start_time)
        else:
            hours_since_last_update = (common.now() - last_updated).total_seconds() / 60 / 60
            volume_config = domains_config.get_cwm_api_volume_config(worker_id=worker_id)
            disable_force_delete = volume_config.disable_force_delete
            disable_force_update = volume_config.disable_force_update
            is_deployed = status == "deployed"
            if not is_deployed:
                if hours_since_last_update >= .5 and revision <= 2:
                    msg = "domain force update (first revision)"
                    if disable_force_update:
                        logs.debug("{} but disable_force_update is true".format(msg), debug_verbosity=10, worker_id=worker_id, start_time=start_time, hours_since_last_update=hours_since_last_update)
                    else:
                        logs.debug(msg, debug_verbosity=4, worker_id=worker_id, start_time=start_time, hours_since_last_update=hours_since_last_update)
                        domains_config.set_worker_force_update(worker_id)
                        if updater_metrics:
                            updater_metrics.not_deployed_force_update(worker_id, start_time)
            else:
                if hours_since_last_update >= config.FORCE_DELETE_GRACE_PERIOD_HOURS and check_worker_force_delete_from_metrics(namespace_name, domains_config):
                    msg = "domain force delete (after grace period + based on metrics)"
                    if disable_force_delete:
                        logs.debug("{} but disable_force_delete is true".format(msg), debug_verbosity=10, worker_id=worker_id, start_time=start_time, hours_since_last_update=hours_since_last_update)
                    else:
                        logs.debug(msg, debug_verbosity=4, worker_id=worker_id, start_time=start_time, hours_since_last_update=hours_since_last_update)
                        domains_config.set_worker_force_delete(worker_id, allow_cancel=True)
                        if updater_metrics:
                            updater_metrics.force_delete(worker_id, start_time)
                elif hours_since_last_update >= config.FORCE_UPDATE_MAX_HOURS_TTL:
                    msg = "domain force update (after FORCE_UPDATE_MAX_HOURS_TTL)"
                    if disable_force_update:
                        logs.debug("{} but disable_force_update is true".format(msg), debug_verbosity=10, worker_id=worker_id, start_time=start_time, hours_since_last_update=hours_since_last_update)
                    else:
                        logs.debug(msg, debug_verbosity=4, worker_id=worker_id, start_time=start_time, hours_since_last_update=hours_since_last_update)
                        domains_config.set_worker_force_update(worker_id)
                        if updater_metrics:
                            updater_metrics.force_update(worker_id, start_time)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), worker_id=worker_id, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        if updater_metrics:
            updater_metrics.exception(worker_id, start_time)
    return worker_id, start_time


def send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager):
    try:
        agg_metrics = domains_config.get_worker_aggregated_metrics(worker_id)
        if agg_metrics:
            current_last_update = common.strptime(agg_metrics.get(metrics_updater.LAST_UPDATE_KEY), metrics_updater.DATEFORMAT)
            current_minutes = agg_metrics.get(metrics_updater.MINUTES_KEY)
            if current_last_update and current_minutes:
                previous_last_update_sent, previous_last_update = domains_config.get_worker_aggregated_metrics_last_sent_update(worker_id)
                if previous_last_update_sent and (common.now() - previous_last_update_sent).total_seconds() < 60:
                    logs.debug('send_agg_metrics: not sending metrics to cwm_api because last update was sent less than 60 seconds ago', debug_verbosity=10, worker_id=worker_id, previous_last_update_sent=previous_last_update_sent)
                elif previous_last_update and previous_last_update == current_last_update:
                    logs.debug('send_agg_metrics: not sending metrics because previous last_update is the same as current last_update', debug_verbosity=10, worker_id=worker_id, previous_last_update=previous_last_update, current_last_update=current_last_update)
                else:
                    logs.debug('send_agg_metrics: sending metrics to cwm_api', debug_verbosity=9, worker_id=worker_id, current_last_update=current_last_update)
                    cwm_api_manager.send_agg_metrics(worker_id, current_minutes)
                    domains_config.set_worker_aggregated_metrics_last_sent_update(worker_id, current_last_update)
            else:
                logs.debug('send_agg_metrics: no last_update or minutes available for domain', debug_verbosity=10, worker_id=worker_id)
        else:
            logs.debug('send_agg_metrics: no agg_metrics for domain', debug_verbosity=10, worker_id=worker_id)
    except Exception as e:
        logs.debug_info("exception: {}".format(e), worker_id=worker_id, start_time=start_time)
        if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
            traceback.print_exc()
        if updater_metrics:
            updater_metrics.exception(worker_id, start_time)


def get_instances_updates(domains_config: DomainsConfig, cwm_api_manager: CwmApiManager):
    last_update = domains_config.keys.updater_last_cwm_api_update.get()
    if last_update:
        from_datetime = common.strptime(last_update.decode(), '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(seconds=1)
    else:
        from_datetime = common.now() - datetime.timedelta(seconds=config.UPDATER_DEFAULT_LAST_UPDATE_DATETIME_SECONDS)
    last_update = None
    instances_updates = {}
    for update in cwm_api_manager.get_cwm_updates(from_datetime):
        if last_update is None or last_update < update['update_time']:
            last_update = update['update_time']
        if update['worker_id'] not in instances_updates:
            if len(cwm_api_manager.volume_config_api_call('id', update['worker_id']).get('errors', [])) > 0:
                instances_updates[update['worker_id']] = 'delete'
            else:
                instances_updates[update['worker_id']] = 'update'
    if last_update:
        domains_config.keys.updater_last_cwm_api_update.set(last_update.strftime('%Y-%m-%dT%H:%M:%S'))
    return instances_updates


def update(namespace_name, last_updated, status, revision,
           worker_id, instance_update, start_time,
           cwm_api_manager=None, domains_config=None, updater_metrics=None):
    if not domains_config:
        domains_config = DomainsConfig()
    if not cwm_api_manager:
        cwm_api_manager = CwmApiManager()
    last_updated = get_datetime_object(last_updated)
    start_time = get_datetime_object(start_time)
    check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision,
                         instance_update, worker_id, start_time)
    send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager)
    return True


class UpdaterMultiprocessor(Multiprocessor):

    def _run_async(self, domains_config, updater_metrics, namespace_name, last_updated, status, revision,
                   worker_id, instance_update, start_time, cwm_api_manager):
        cmd = [
            'cwm-worker-operator', 'updater', 'update',
            '--namespace-name', namespace_name,
            '--last-updated', get_datetime_string(last_updated) if last_updated else '',
            '--status', str(status) if status else '',
            '--revision', str(revision) if revision else '',
            '--worker-id', worker_id,
            '--instance-update', instance_update if instance_update else '',
            '--start-time', get_datetime_string(start_time) if start_time else ''
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def _run_sync(self, domains_config, updater_metrics, namespace_name, last_updated, status, revision,
                  worker_id, instance_update, start_time, cwm_api_manager):
        update(
            namespace_name, last_updated, status, revision,
            worker_id, instance_update, start_time,
            cwm_api_manager=cwm_api_manager, domains_config=domains_config, updater_metrics=updater_metrics
        )

    def _get_process_key(self, domains_config, updater_metrics, namespace_name, last_updated, status, revision,
                         worker_id, instance_update, start_time, cwm_api_manager):
        return worker_id


def run_single_iteration(domains_config, metrics, deployments_manager, cwm_api_manager, is_async=False, **_):
    multiprocessor = UpdaterMultiprocessor(config.UPDATER_MAX_PARALLEL_DEPLOY_PROCESSES if is_async else 1)
    updater_metrics = metrics
    instances_updates = get_instances_updates(domains_config, cwm_api_manager)
    all_releases = {release["namespace"]: release for release in deployments_manager.iterate_all_releases()}
    for release in all_releases.values():
        namespace_name = release["namespace"]
        datestr, timestr, *_ = release["updated"].split(" ")
        last_updated = common.strptime("{}T{}".format(datestr, timestr.split(".")[0]), "%Y-%m-%dT%H:%M:%S")
        status = release["status"]
        # app_version = release["app_version"]
        revision = int(release["revision"])
        start_time = common.now()
        worker_id = common.get_worker_id_from_namespace_name(namespace_name)
        instance_update = instances_updates.get(worker_id)
        multiprocessor.process(domains_config, updater_metrics, namespace_name, last_updated, status, revision,
                               worker_id, instance_update, start_time, cwm_api_manager)
        # worker_id, start_time = check_update_release(domains_config, updater_metrics, namespace_name, last_updated, status, revision, instances_updates)
        # send_agg_metrics(domains_config, updater_metrics, worker_id, start_time, cwm_api_manager)
    multiprocessor.finalize()


def start_daemon(once=False, with_prometheus=True, updater_metrics=None, domains_config=None, deployments_manager=None, cwm_api_manager=None):
    if cwm_api_manager is None:
        cwm_api_manager = CwmApiManager()
    Daemon(
        name='updater',
        sleep_time_between_iterations_seconds=config.UPDATER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.UpdaterMetrics,
        domains_config=domains_config,
        metrics=updater_metrics,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_UPDATER,
        run_single_iteration_extra_kwargs={'cwm_api_manager': cwm_api_manager, 'is_async': True},
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
