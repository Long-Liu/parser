"""Template config loading with input validation and in-process caching."""

import fnmatch
import os

import yaml

from contexts.template.infrastructure.validators import TEMPLATE_ID_RE

DEFAULT_CONFIG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "templates")
)

_config_cache: dict[str, tuple[float, dict]] = {}


def _config_dir(config_dir=None):
    path = config_dir or DEFAULT_CONFIG_DIR
    return os.path.abspath(path)


def load_config(template_id: str, config_dir=None) -> dict:
    """Load a single template config by id. Raises ValueError on invalid id."""
    if not TEMPLATE_ID_RE.match(template_id):
        raise ValueError(f"invalid template_id: {template_id}")

    filepath = os.path.join(_config_dir(config_dir), f"{template_id}.yaml")
    resolved = os.path.realpath(filepath)
    if not resolved.startswith(os.path.realpath(_config_dir(config_dir))):
        raise ValueError(f"path traversal blocked: {template_id}")

    if not os.path.exists(resolved):
        raise FileNotFoundError(f"Config not found: {resolved}")

    with open(resolved, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_configs(config_dir=None) -> list[dict]:
    """List all template configs (cached in-process; cleared on restart)."""
    result = []
    d = _config_dir(config_dir)
    if not os.path.isdir(d):
        return result
    for filename in os.listdir(d):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(d, filename)
            mtime = os.path.getmtime(filepath)
            if filepath in _config_cache and _config_cache[filepath][0] == mtime:
                result.append(_config_cache[filepath][1])
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            _config_cache[filepath] = (mtime, cfg)
            result.append(cfg)
    return result


def match_template(sheet_name: str, config_dir=None) -> dict | None:
    """Match a sheet name to a template config via shell-style patterns."""
    configs = list_configs(config_dir)
    for cfg in configs:
        pattern = cfg.get("sheet_pattern", "")
        if pattern and fnmatch.fnmatch(sheet_name, pattern):
            return cfg
    return None
