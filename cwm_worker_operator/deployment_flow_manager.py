from cwm_worker_operator.domains_config import DomainsConfig


class InitializerDeploymentFlowManager:

    def __init__(self, domains_config: DomainsConfig):
        self.domains_config = domains_config
        self.hostnames_forced_update = set()

    def iterate_worker_ids_forced_update(self):
        for worker_id in self.domains_config.get_worker_ids_force_update():
            if self.domains_config.keys.worker_ready_for_deployment.exists(worker_id):
                continue
            if self.domains_config.keys.worker_waiting_for_deployment_complete.exists(worker_id):
                continue
            yield worker_id

    def add_hostname_forced_update(self, hostname):
        self.hostnames_forced_update.add(hostname)

    def iterate_hostnames_waiting_for_initialization(self):
        for hostname in self.domains_config.get_hostnames_waiting_for_initlization():
            if hostname in self.hostnames_forced_update:
                continue
            yield hostname

    def is_worker_id_valid_for_initialization(self, worker_id):
        return (
            not self.domains_config.keys.worker_ready_for_deployment.exists(worker_id)
            and not self.domains_config.keys.worker_waiting_for_deployment_complete.exists(worker_id)
            and not self.domains_config.keys.worker_force_update.exists(worker_id)
        )


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
        for hostname in hostnames:
            if self.domains_config.keys.hostname_initialize.exists(hostname):
                return True
        print('WARNING! worker_id is not marked for force_update and none of the hostnames are waiting to initialize:'
              'deleting ready for deployment key and skipping')
        self.domains_config.keys.worker_ready_for_deployment.delete(worker_id)
        return False


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
