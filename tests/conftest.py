import pytest
from .mocks.domains_config import MockDomainsConfig
from .mocks.metrics import MockInitializerMetrics, MockDeployerMetrics, MockWaiterMetrics
from .mocks.deployments_manager import MockDeploymentsManager


ORDERED_TESTS = [
    'tests/test_domains_config.py',
    'tests/test_deployments_manager.py',
    'tests/test_deploy_e2e.py',
    'tests/test_deploy_k8s.py',
]


def pytest_collection_modifyitems(session, config, items):
    ordered_items = []
    for item in items:
        if item.location[0] not in ORDERED_TESTS:
            ordered_items.append(item)
    for item_location in ORDERED_TESTS:
        for item in items:
            if item.location[0] == item_location:
                ordered_items.append(item)
    items[:] = ordered_items


@pytest.fixture()
def domains_config():
    return MockDomainsConfig()


@pytest.fixture()
def deployments_manager():
    return MockDeploymentsManager()

@pytest.fixture()
def initializer_metrics():
    return MockInitializerMetrics()


@pytest.fixture()
def deployer_metrics():
    return MockDeployerMetrics()


@pytest.fixture()
def waiter_metrics():
    return MockWaiterMetrics()
