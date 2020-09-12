import time

from cwm_worker_operator import config
from cwm_worker_operator import metrics
from cwm_worker_operator import deployer


def start(once=False):
    deployer.init_cache()
    redis_pool = config.get_redis_pool()
    errorhandler_metrics = metrics.Metrics(config.METRICS_GROUP_ERRORHANDLER_PATH_SUFFIX)
    while True:
        errorhandler_metrics.send("iterations started", debug_verbosity=8)
        error_domain_names = config.get_error_worker_domains(redis_pool)
        namespaces = {}
        domains_error_attempt_numbers = {}
        for domain_name in error_domain_names:
            error_attempt_number = domains_error_attempt_numbers[domain_name] = config.get_worker_error_attempt_number(redis_pool, domain_name)
            if error_attempt_number > config.WORKER_ERROR_MAX_ATTEMPTS:
                continue
            deployer.init_domain_waiting_for_deploy(redis_pool, domain_name, errorhandler_metrics, namespaces, error_attempt_number)
        namespaces_deployed = set()
        for namespace_name, namespace_config in namespaces.items():
            deployer.deploy_namespace(redis_pool, namespace_name, namespace_config, errorhandler_metrics, namespaces_deployed, domains_error_attempt_numbers)
        deployer.wait_for_namespaces_deployed(redis_pool, namespaces_deployed, namespaces, errorhandler_metrics, config.ERRORHANDLER_WAIT_DEPLOYMENT_READY_MAX_SECONDS, domains_error_attempt_numbers)
        errorhandler_metrics.send("iterations ended", debug_verbosity=8)
        if once:
            errorhandler_metrics.save(force=True)
            break
        errorhandler_metrics.save()
        time.sleep(config.ERRORHANDLER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS)
