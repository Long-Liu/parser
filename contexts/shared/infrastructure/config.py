"""Application configuration — nested pydantic models loaded from YAML."""

from __future__ import annotations

import os

import yaml
from pydantic import BaseModel, Field


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


class AuthConfig(BaseModel):
    """Authentication behaviour switches."""

    # False (default): POST /api/auth/register requires an admin token with the
    # user:manage permission. True: anyone can register (open registration).
    allow_open_register: bool = False


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
    auth: AuthConfig = Field(default_factory=AuthConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)


# ── loader ──────────────────────────────────────────────────────────────────


def _discover_config_dir() -> str:
    """Walk up from this file to find the project root ``config/`` directory."""
    candidate = os.path.dirname(__file__)
    for _ in range(8):
        candidate = os.path.dirname(candidate)
        path = os.path.join(candidate, "config")
        if os.path.isdir(path):
            return path
    raise FileNotFoundError("Cannot locate config/ directory")


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
