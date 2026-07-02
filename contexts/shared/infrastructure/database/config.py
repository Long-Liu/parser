"""Application configuration loaded from YAML with env-var overrides for secrets."""

import os
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Config:
    DEBUG: bool
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int
    SECRET_KEY: str
    JWT_EXPIRY_HOURS: int

def load_config(env: str | None = None) -> Config:
    """Load YAML config for *env*, with secrets preferentially from environment variables."""
    env = env or os.getenv("APP_ENV", "local")
    # Walk up from this file to find the project root with a config/ directory
    config_dir = os.environ.get("CONFIG_DIR")
    if not config_dir:
        candidate = os.path.dirname(__file__)
        for _ in range(8):
            candidate = os.path.dirname(candidate)
            path = os.path.join(candidate, "config", f"{env}.yaml")
            if os.path.exists(path):
                config_dir = os.path.join(candidate, "config")
                break
        else:
            raise FileNotFoundError("Cannot locate config/ directory — set CONFIG_DIR env var")
    else:
        path = os.path.join(config_dir, f"{env}.yaml")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    db_password = os.getenv("DB_PASSWORD") or data["db"].get("password", "")
    jwt_secret = os.getenv("JWT_SECRET") or data["jwt"].get("secret", "")
    if env != "local":
        if not db_password:
            raise ValueError("DB_PASSWORD is required outside local environment")
        if len(jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters outside local environment")

    return Config(
        DEBUG=data.get("debug", False),
        DB_HOST=data["db"]["host"],
        DB_PORT=data["db"]["port"],
        DB_USER=data["db"]["user"],
        DB_PASSWORD=db_password,
        DB_NAME=data["db"]["database"],
        DB_POOL_SIZE=data["db"]["pool_size"],
        SECRET_KEY=jwt_secret,
        JWT_EXPIRY_HOURS=data["jwt"]["expiry_hours"],
    )
