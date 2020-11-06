from ruamel import yaml

from cwm_worker_operator import config


def test_operator_config_values():
    with open("helm/values.yaml") as f:
        values = yaml.safe_load(f)
    missing_keys = []
    for key in dir(config):
        if key.startswith("__") or key in ["base64", "json", "os"]:
            continue
        if key in ["PULL_SECRET"]:
            continue
        if key in ["CWM_WORKER_DEPLOYMENT_EXTRA_CONFIG", "CWM_WORKER_EXTRA_OBJECTS", "MINIO_EXTRA_CONFIG"]:
            key = key + "_JSON"
        elif key == "DEBUG_VERBOSITY":
            key = "debugVerbosity"
        if key in values or key.lower() in values or key in values['operator']:
            assert True
        else:
            missing_keys.append(key)
    if len(missing_keys) > 0:
        assert False, "Missing keys: {}".format(missing_keys)

