from __future__ import annotations

# Tortoise ORM lifecycle.

import logging

from tortoise import Tortoise, connections

from contexts.shared.infrastructure.database.config import Config

logger = logging.getLogger("parser.db")

_initialized = False

_MODEL_MODULES = [
    "contexts.alert.infrastructure.tables",
    "contexts.auth.infrastructure.tables",
    "contexts.project.infrastructure.tables",
    "contexts.parsing.infrastructure.tables",
    "contexts.template.infrastructure.tables",
    "contexts.shared.infrastructure.database.tables",
]

MIGRATIONS_MODULE = "contexts.shared.infrastructure.database.migrations"


def tortoise_config(config: Config) -> dict:
    """Build the single Tortoise config used by the app and migration CLI."""
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.mysql",
                "credentials": {
                    "host": config.DB_HOST,
                    "port": config.DB_PORT,
                    "user": config.DB_USER,
                    "password": config.DB_PASSWORD,
                    "database": config.DB_NAME,
                    "charset": "utf8mb4",
                    "maxsize": config.DB_POOL_SIZE,
                },
            }
        },
        "apps": {
            "models": {
                "models": _MODEL_MODULES,
                "default_connection": "default",
                "migrations": MIGRATIONS_MODULE,
            }
        },
    }


async def init(config: Config) -> None:
    """Initialize Tortoise connections and model registry."""
    global _initialized
    if _initialized:
        await close()

    await Tortoise.init(config=tortoise_config(config))
    _initialized = True


async def close() -> None:
    """Close all Tortoise connections."""
    global _initialized
    if _initialized:
        await connections.close_all()
        _initialized = False


def ensure_initialized() -> None:
    if not _initialized:
        raise RuntimeError("db.init() must be called first")
