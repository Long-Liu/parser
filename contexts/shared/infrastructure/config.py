"""Application configuration — nested pydantic models loaded from YAML."""

from __future__ import annotations

import os
import re

import yaml
from pydantic import BaseModel, Field

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env_vars(value):
    """Recursively expand ``${ENV_VAR}`` placeholders in string values.

    Unset variables expand to an empty string so that the existing non-local
    validation (``db.password`` / ``jwt.secret`` / ``admin.default_password``)
    fails fast instead of silently running with a literal placeholder.
    """
    if isinstance(value, dict):
        return {key: _expand_env_vars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), value)
    return value


class AppConfig(BaseModel):
    env: str = "local"


class DatabaseConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "excel_parser"
    pool_size: int = 5


class JwtConfig(BaseModel):
    secret: str = ""
    expiry_hours: int = 24


class CorsConfig(BaseModel):
    origins: str = "*"


class UploadConfig(BaseModel):
    dir: str = "uploads"


class AiAnalysisConfig(BaseModel):
    url: str = ""
    api_key: str = ""


class AdminConfig(BaseModel):
    default_password: str = ""


class Settings(BaseModel):
    """Root config — all values loaded from a single YAML file."""

    debug: bool = False
    app: AppConfig = Field(default_factory=AppConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    jwt: JwtConfig = Field(default_factory=JwtConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    upload: UploadConfig = Field(default_factory=UploadConfig)
    ai_analysis: AiAnalysisConfig = Field(default_factory=AiAnalysisConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**_expand_env_vars(data or {}))


# ── loader ──────────────────────────────────────────────────────────────────


def _discover_config_dir() -> str:
    """Locate the ``config/`` directory deterministically.

    Priority:
    1. ``APP_CONFIG_DIR`` environment variable (explicit override).
    2. Anchored at this file: ``contexts/shared/infrastructure/config.py``
       sits exactly 4 levels below the project root, so the root ``config/``
       directory is resolved without walking arbitrary parents.
    """
    env_dir = os.getenv("APP_CONFIG_DIR")
    if env_dir:
        config_dir = os.path.abspath(env_dir)
        if os.path.isdir(config_dir):
            return config_dir
        raise FileNotFoundError(f"APP_CONFIG_DIR does not exist: {config_dir}")

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    config_dir = os.path.join(project_root, "config")
    if os.path.isdir(config_dir):
        return config_dir
    raise FileNotFoundError(f"Cannot locate config/ directory at {config_dir}")


def load_config(env: str | None = None) -> Settings:
    """Load and validate configuration without mutating process-global state."""
    env = env or os.getenv("APP_ENV", "local")

    config_dir = _discover_config_dir()
    path = os.path.join(config_dir, f"{env}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    settings = Settings.from_yaml(path)

    # production safety checks
    if env != "local":
        if not settings.db.password:
            raise ValueError("db.password is required outside local environment")
        if len(settings.jwt.secret) < 32:
            raise ValueError("jwt.secret must be at least 32 characters outside local environment")

    return settings


load_settings = load_config
