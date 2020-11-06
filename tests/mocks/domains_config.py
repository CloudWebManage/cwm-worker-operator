import datetime
from collections import defaultdict
from cwm_worker_operator.domains_config import DomainsConfig


class MockDomainsConfig(DomainsConfig):

    def __init__(self):
        self.worker_domains_ready_for_deployment = []
        self.worker_domains_waiting_for_deployment_complete = []
        self.worker_domains_waiting_for_initlization = []
        self.domain_cwm_api_volume_config = {}
        self.domain_worker_error = {}
        self.domain_worker_error_attempt_number = defaultdict(int)
        self.domain_worker_ready_for_deployment = {}
        self.domain_ready_for_deployment_start_time = {}
        self.domain_volume_config_namespace = {}
        self.domain_worker_waiting_for_deployment = {}
        self.domain_worker_available_hostname = {}
        self.domain_deleted_worker_keys = {}
        self.domains_to_delete = []
        self.domain_worker_force_update_calls = {}
        self.domain_worker_force_delete_calls = {}
        self.worker_domains_force_update = []
        self.get_cwm_api_volume_config_calls = {}

    def get_worker_domains_ready_for_deployment(self):
        return self.worker_domains_ready_for_deployment

    def get_worker_domains_waiting_for_deployment_complete(self):
        return self.worker_domains_waiting_for_deployment_complete

    def get_worker_domains_waiting_for_initlization(self):
        return self.worker_domains_waiting_for_initlization

    def get_cwm_api_volume_config(self, domain_name, metrics=None, force_update=False):
        self.get_cwm_api_volume_config_calls.setdefault(domain_name, []).append({"force_update": force_update})
        return self.domain_cwm_api_volume_config.get(domain_name, {})

    def set_worker_error(self, domain_name, error_msg):
        self.domain_worker_error[domain_name] = error_msg

    def increment_worker_error_attempt_number(self, domain_name):
        self.domain_worker_error_attempt_number[domain_name] += 1
        return self.domain_worker_error_attempt_number[domain_name]

    def set_worker_ready_for_deployment(self, domain_name):
        self.domain_worker_ready_for_deployment[domain_name] = True

    def get_worker_ready_for_deployment_start_time(self, domain_name):
        return self.domain_ready_for_deployment_start_time.get(domain_name, datetime.datetime.now())

    def get_volume_config_namespace_from_domain(self, metrics, domain_name):
        return self.domain_volume_config_namespace.get(domain_name)

    def set_worker_waiting_for_deployment(self, domain_name):
        self.domain_worker_waiting_for_deployment[domain_name] = True

    def set_worker_available(self, domain_name, hostname):
        self.domain_worker_available_hostname[domain_name] = hostname

    def del_worker_keys(self, redis_connection, domain_name, **kwargs):
        self.domain_deleted_worker_keys[domain_name] = kwargs

    def iterate_domains_to_delete(self):
        for domain in self.domains_to_delete:
            yield domain

    def set_worker_force_update(self, domain_name):
        self.domain_worker_force_update_calls.setdefault(domain_name, []).append(True)

    def set_worker_force_delete(self, domain_name):
        self.domain_worker_force_delete_calls.setdefault(domain_name, []).append(True)

    def get_domains_force_update(self):
        return self.worker_domains_force_update
