import time
import signal

import prometheus_client

from cwm_worker_operator import logs
from cwm_worker_operator.domains_config import DomainsConfig
from cwm_worker_operator.deployments_manager import DeploymentsManager


class Daemon:

    def __init__(self, name, sleep_time_between_iterations_seconds,
                 metrics_class=None, domains_config=None, metrics=None, run_single_iteration_callback=None,
                 prometheus_metrics_port=None, run_single_iteration_extra_kwargs=None,
                 deployments_manager=None, run_initialization_callback=None):
        self.name = name
        self.metrics = metrics if metrics else (metrics_class() if metrics_class else None)
        self.domains_config = domains_config if domains_config else DomainsConfig()
        self.run_single_iteration_callback = run_single_iteration_callback
        self.run_initialization_callback = run_initialization_callback
        self.prometheus_metrics_port = prometheus_metrics_port
        self.sleep_time_between_iterations_seconds = sleep_time_between_iterations_seconds
        self.run_single_iteration_extra_kwargs = {} if run_single_iteration_extra_kwargs is None else run_single_iteration_extra_kwargs
        self.deployments_manager = deployments_manager if deployments_manager else DeploymentsManager()
        self.terminate_requested = False

    def start(self, once=False, with_prometheus=None):
        if with_prometheus is None:
            with_prometheus = bool(self.prometheus_metrics_port)
        with logs.alert_exception_catcher(self.domains_config, daemon=self.name):
            if with_prometheus:
                prometheus_client.start_http_server(self.prometheus_metrics_port)
            if self.run_initialization_callback:
                self.run_initialization_callback(
                    domains_config=self.domains_config,
                    metrics=self.metrics,
                    deployments_manager=self.deployments_manager,
                    **self.run_single_iteration_extra_kwargs
                )
            if once:
                self.run_single_iteration(**self.run_single_iteration_extra_kwargs)
            else:
                self.start_main_loop()

    def on_sigterm(self, *args, **kwargs):
        logs.debug_info(f"SIGTERM received for daemon {self.name}")
        self.terminate_requested = True

    def start_main_loop(self):
        signal.signal(signal.SIGTERM, self.on_sigterm)
        while not self.terminate_requested:
            self.run_single_iteration(**self.run_single_iteration_extra_kwargs)
            if self.terminate_requested:
                break
            time.sleep(self.sleep_time_between_iterations_seconds)
        assert self.terminate_requested, f'Unexpected termination of daemon {self.name}'
        logs.debug_info(f"Graceful termination of daemon {self.name}")

    def run_single_iteration(self, **kwargs):
        self.run_single_iteration_callback(
            domains_config=self.domains_config,
            metrics=self.metrics,
            deployments_manager=self.deployments_manager,
            daemon=self,
            **kwargs
        )
