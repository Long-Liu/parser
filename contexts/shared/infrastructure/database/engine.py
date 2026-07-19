from __future__ import annotations

# Tortoise ORM lifecycle.

import logging

from tortoise import Tortoise, connections

from contexts.shared.infrastructure.config import Settings

logger = logging.getLogger("parser.db")

_initialized = False

_MODEL_MODULES = [
    "contexts.alert.infrastructure.tables",
    "contexts.auth.infrastructure.tables",
    "contexts.project.infrastructure.tables",
    "contexts.parsing.infrastructure.tables",
    "contexts.shared.infrastructure.database.tables",
]

MIGRATIONS_MODULE = "contexts.shared.infrastructure.database.migrations"


def tortoise_config(config: Settings) -> dict:
    """Build the single Tortoise config used by the app and migration CLI."""
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.mysql",
                "credentials": {
                    "host": config.db.host,
                    "port": config.db.port,
                    "user": config.db.user,
                    "password": config.db.password,
                    "database": config.db.database,
                    "charset": "utf8mb4",
                    "maxsize": config.db.pool_size,
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


async def init(config: Settings) -> None:
    """Initialize Tortoise connections and model registry."""
    global _initialized
    if _initialized:
        await close()

    await Tortoise.init(config=tortoise_config(config), _enable_global_fallback=True)
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
