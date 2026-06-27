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
    path = os.path.join(os.path.dirname(__file__), "..", "config", f"{env}.yaml")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    db_password = os.getenv("DB_PASSWORD") or data["db"].get("password", "")
    jwt_secret = os.getenv("JWT_SECRET") or data["jwt"].get("secret", "")

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