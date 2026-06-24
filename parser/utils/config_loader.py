import os
import fnmatch
import yaml

DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "configs", "templates")


def _config_dir(config_dir=None):
    path = config_dir or DEFAULT_CONFIG_DIR
    return os.path.abspath(path)


def load_config(template_id: str, config_dir=None) -> dict:
    filepath = os.path.join(_config_dir(config_dir), f"{template_id}.yaml")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_configs(config_dir=None) -> list[dict]:
    result = []
    d = _config_dir(config_dir)
    if not os.path.isdir(d):
        return result
    for filename in os.listdir(d):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(d, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                result.append(yaml.safe_load(f))
    return result


def match_template(sheet_name: str, config_dir=None) -> dict | None:
    configs = list_configs(config_dir)
    for cfg in configs:
        pattern = cfg.get("sheet_pattern", "")
        if fnmatch.fnmatch(sheet_name, pattern):
            return cfg
    return None
