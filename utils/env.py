import os
import yaml


def load_env_variables(config_file: str) -> None:
    with open(config_file, "r", encoding="utf-8") as conf_file:
        env_variables = yaml.safe_load(conf_file)["environment"]
    for key, value in env_variables.items():
        os.environ[key] = value
