"""
Deletes worker deployments
"""
import json
import traceback

from cwm_worker_operator import logs
from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager
from cwm_worker_operator import common
from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator.updater import CONFIRM_FORCE_DELETE_DATA


def get_delete_data_config(namespace_name):
    if config.DELETER_DATA_DELETE_CONFIG:
        return json.loads(json.dumps(config.DELETER_DATA_DELETE_CONFIG).replace('__NAMESPACE_NAME__', namespace_name))
    else:
        return config.DELETER_DATA_DELETE_CONFIG


def delete(worker_id=None, deployment_timeout_string=None, delete_namespace=None, delete_helm=None,
           domains_config=None, deployments_manager=None, with_metrics=False, hostname=None,
           force_now=False):
    if domains_config is None:
        domains_config = DomainsConfig()
    if deployments_manager is None:
        deployments_manager = DeploymentsManager()
    if delete_namespace is None:
        delete_namespace = config.DELETER_DEFAULT_DELETE_NAMESPACE
    if delete_helm is None:
        delete_helm = config.DELETER_DEFAULT_DELETE_HELM
    if hostname:
        assert not worker_id, 'cannot specify both worker_id and hostname'
        try:
            worker_id = domains_config.get_cwm_api_volume_config(hostname=hostname).id
        except:
            pass
        domains_config.del_worker_hostname_keys(hostname)
    else:
        assert worker_id, 'must specify either worker_id or hostname'
    if worker_id:
        delete_data = domains_config.keys.worker_force_delete_data.get(worker_id) == CONFIRM_FORCE_DELETE_DATA.encode()
        domains_config.del_worker_keys(
            worker_id,
            with_metrics=True if delete_data else with_metrics,
        )
        namespace_name = common.get_namespace_name_from_worker_id(worker_id)
        delete_kwargs = dict(
            timeout_string=deployment_timeout_string,
            delete_namespace=delete_namespace,
            delete_helm=delete_helm,
            delete_data=delete_data,
            delete_data_config=get_delete_data_config(namespace_name) if delete_data else None,
            force_now=force_now
        )
        logs.debug_info('deleting instance',
                        namespace_name=namespace_name, worker_id=worker_id,
                        **delete_kwargs)
        deployments_manager.delete(namespace_name, "minio", **delete_kwargs)
        if delete_data:
            domains_config.keys.worker_force_delete_data.delete(worker_id)
    return True


def run_single_iteration(domains_config, metrics, deployments_manager, **_):
    deleter_metrics = metrics
    for worker_to_delete in domains_config.iterate_domains_to_delete():
        worker_id = worker_to_delete['worker_id']
        allow_cancel = worker_to_delete['allow_cancel']
        start_time = common.now()
        try:
            if allow_cancel and domains_config.is_worker_waiting_for_deployment(worker_id):
                domains_config.del_worker_force_delete(worker_id)
                deleter_metrics.delete_canceled(worker_id, start_time)
            else:
                delete(worker_id, domains_config=domains_config, deployments_manager=deployments_manager)
                deleter_metrics.delete_success(worker_id, start_time)
        except Exception as e:
            logs.debug_info("exception: {}".format(e), worker_id=worker_id, start_time=start_time)
            if config.DEBUG and config.DEBUG_VERBOSITY >= 3:
                traceback.print_exc()
            deleter_metrics.exception(worker_id, start_time)


def start_daemon(once=False, with_prometheus=True, deleter_metrics=None, domains_config=None, deployments_manager=None):
    Daemon(
        name='deleter',
        sleep_time_between_iterations_seconds=config.DELETER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        metrics_class=metrics.DeleterMetrics,
        domains_config=domains_config,
        metrics=deleter_metrics,
        run_single_iteration_callback=run_single_iteration,
        prometheus_metrics_port=config.PROMETHEUS_METRICS_PORT_DELETER,
        deployments_manager=deployments_manager
    ).start(
        once=once,
        with_prometheus=with_prometheus
    )
