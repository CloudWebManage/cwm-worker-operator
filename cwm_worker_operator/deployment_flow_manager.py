from cwm_worker_operator import config
from cwm_worker_operator import common
from cwm_worker_operator.domains_config import DomainsConfig


class InitializerDeploymentFlowManager:

    def __init__(self, domains_config: DomainsConfig):
        self.domains_config = domains_config
        self.hostnames_forced_update = set()

    def iterate_volume_configs_forced_update(self, metrics):
        for worker_id in self.domains_config.get_worker_ids_force_update():
            volume_config = self.domains_config.get_cwm_api_volume_config(worker_id=worker_id, force_update=True, metrics=metrics)
            for hostname in volume_config.hostnames:
                self.hostnames_forced_update.add(hostname)
            if self.domains_config.keys.worker_ready_for_deployment.exists(worker_id):
                # worker is already ready for deployment, no need to initialize
                continue
            if self.domains_config.keys.worker_waiting_for_deployment_complete.exists(worker_id):
                # worker is already waiting for deployment to complete, no need to initialize
                continue
            yield volume_config, worker_id

    def iterate_volume_config_hostnames_waiting_for_initialization(self, metrics):
        for hostname in self.domains_config.get_hostnames_waiting_for_initlization():
            if hostname in self.hostnames_forced_update:
                # hostname was already handled in the forced updates
                continue
            volume_config = self.domains_config.get_cwm_api_volume_config(hostname=hostname, metrics=metrics)
            worker_id = volume_config.id
            if not worker_id or volume_config._error:
                yield volume_config, hostname, True
            elif (
                self.domains_config.keys.worker_ready_for_deployment.exists(worker_id)
                or self.domains_config.keys.worker_waiting_for_deployment_complete.exists(worker_id)
                or self.domains_config.keys.worker_force_update.exists(worker_id)
            ):
                # worker is already handled in other flow steps
                continue
            else:
                yield volume_config, hostname, False

    def set_worker_ready_for_deployment(self, worker_id):
        self.domains_config.set_worker_ready_for_deployment(worker_id)

    def set_hostname_error(self, hostname, error_msg, allow_retry=False):
        if allow_retry:
            error_attempt_number = self.domains_config.increment_worker_error_attempt_number(hostname)
            if error_attempt_number >= config.WORKER_ERROR_MAX_ATTEMPTS:
                self.domains_config.set_worker_error_by_hostname(hostname, error_msg)
        else:
            self.domains_config.set_worker_error_by_hostname(hostname, error_msg)

    def set_worker_force_delete(self, worker_id):
        self.domains_config.del_worker_force_update(worker_id)
        self.domains_config.set_worker_force_delete(worker_id)


class DeployerDeploymentFlowManager:

    def __init__(self, domains_config: DomainsConfig):
        self.domains_config = domains_config

    def iterate_worker_ids_ready_for_deployment(self):
        for worker_id in self.domains_config.get_worker_ids_ready_for_deployment():
            if self.domains_config.keys.worker_waiting_for_deployment_complete.exists(worker_id):
                continue
            yield worker_id

    def is_valid_worker_hostnames_for_deployment(self, worker_id, hostnames):
        if self.domains_config.keys.worker_force_update.exists(worker_id):
            return True
        for request_hostname in self.domains_config.keys.hostname_initialize.iterate_prefix_key_suffixes():
            if common.is_hostnames_match_in_list(request_hostname, hostnames):
                return True
        print('WARNING! worker_id is not marked for force_update and none of the hostnames are waiting to initialize:'
              'deleting ready for deployment key and skipping')
        self.domains_config.keys.worker_ready_for_deployment.delete(worker_id)
        return False

    def set_worker_error(self, worker_id, error_msg):
        self.domains_config.set_worker_error(worker_id, error_msg)

    def wait_retry_deployment(self, worker_id):
        self.domains_config.increment_worker_deployment_attempt_number(worker_id)
        self.domains_config.set_worker_waiting_for_deployment(worker_id, wait_for_error=True)

    def set_worker_waiting_for_deployment(self, worker_id):
        self.domains_config.set_worker_waiting_for_deployment(worker_id)


class WaiterDeploymentFlowManager:

    def __init__(self, domains_config: DomainsConfig):
        self.domains_config = domains_config

    def iterate_worker_ids_waiting_for_deployment_complete(self):
        for worker_id in self.domains_config.get_worker_ids_waiting_for_deployment_complete():
            if not self.domains_config.keys.worker_ready_for_deployment.exists(worker_id):
                print('WARNING! worker_id does not have ready for deployment key: deleting waiting for deployment key and skipping')
                self.domains_config.keys.worker_waiting_for_deployment_complete.delete(worker_id)
                continue
            yield worker_id

    def set_worker_error(self, worker_id, error_msg):
        self.domains_config.set_worker_error(worker_id, error_msg)

    def set_worker_wait_for_error_complete(self, worker_id):
        self.domains_config.keys.worker_waiting_for_deployment_complete.delete(worker_id)

    def set_worker_available(self, worker_id, internal_hostname):
        self.domains_config.set_worker_available(worker_id, internal_hostname)
