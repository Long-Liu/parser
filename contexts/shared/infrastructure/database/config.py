"""Application configuration loaded from YAML."""

import os
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Config:
    DEBUG: bool
    APP_ENV: str
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int
    SECRET_KEY: str
    JWT_EXPIRY_HOURS: int
    CORS_ORIGINS: str
    UPLOAD_DIR: str
    AI_ANALYSIS_URL: str
    AI_ANALYSIS_API_KEY: str
    DEFAULT_ADMIN_PASSWORD: str


_config: Config | None = None


def get_config(key: str) -> str:
    """Return a config value by field name.  Call ``load_config()`` first."""
    if _config is None:
        raise RuntimeError("config not loaded — call load_config() first")
    return str(getattr(_config, key))


def _discover_config_dir() -> str:
    """Walk up from this file to find the project root ``config/`` directory."""
    candidate = os.path.dirname(__file__)
    for _ in range(8):
        candidate = os.path.dirname(candidate)
        path = os.path.join(candidate, "config")
        if os.path.isdir(path):
            return path
    raise FileNotFoundError("Cannot locate config/ directory")


def load_config(env: str | None = None) -> Config:
    """Load YAML config for *env*.  All values (including secrets) come from
    the YAML file — no environment-variable overrides."""
    global _config
    env = env or os.getenv("APP_ENV", "local")

    config_dir = _discover_config_dir()
    path = os.path.join(config_dir, f"{env}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    db_password = data["db"].get("password", "")
    jwt_secret = data["jwt"].get("secret", "")
    if env != "local":
        if not db_password:
            raise ValueError("db.password is required outside local environment")
        if len(jwt_secret) < 32:
            raise ValueError("jwt.secret must be at least 32 characters outside local environment")

    _config = Config(
        DEBUG=data.get("debug", False),
        APP_ENV=data.get("app", {}).get("env", env),
        DB_HOST=data["db"]["host"],
        DB_PORT=data["db"]["port"],
        DB_USER=data["db"]["user"],
        DB_PASSWORD=db_password,
        DB_NAME=data["db"]["database"],
        DB_POOL_SIZE=data["db"]["pool_size"],
        SECRET_KEY=jwt_secret,
        JWT_EXPIRY_HOURS=data["jwt"]["expiry_hours"],
        CORS_ORIGINS=data.get("cors", {}).get("origins", ""),
        UPLOAD_DIR=data.get("upload", {}).get("dir", "uploads"),
        AI_ANALYSIS_URL=data.get("ai_analysis", {}).get("url", ""),
        AI_ANALYSIS_API_KEY=data.get("ai_analysis", {}).get("api_key", ""),
        DEFAULT_ADMIN_PASSWORD=data.get("admin", {}).get("default_password", ""),
    )
    return _config
