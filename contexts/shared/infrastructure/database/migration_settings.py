"""Configuration entry point for the Tortoise migration CLI.

Usage:
    tortoise -c contexts.shared.infrastructure.database.migration_settings.TORTOISE_ORM init
    tortoise -c contexts.shared.infrastructure.database.migration_settings.TORTOISE_ORM makemigrations
    tortoise -c contexts.shared.infrastructure.database.migration_settings.TORTOISE_ORM migrate
"""

from contexts.shared.infrastructure.config import load_config
from contexts.shared.infrastructure.database.engine import tortoise_config

TORTOISE_ORM = tortoise_config(load_config())
