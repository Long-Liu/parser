from __future__ import annotations

# DDL helpers for Tortoise models.

from contexts.shared.infrastructure.database.engine import ensure_initialized
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS


async def migrate_db(config):
    """Apply committed Tortoise migrations; never create tables from models."""
    ensure_initialized()
    from tortoise.migrations.api import migrate
    from contexts.shared.infrastructure.database.engine import tortoise_config

    await migrate(
        config=tortoise_config(config),
        app_labels=["models"],
        direction="forward",
    )


async def create_data_table(template_id: str):
    """Validate that a template data table model is registered.

    This hook is kept for the existing bootstrap flow and fails fast on unknown
    templates. The table itself must be introduced by a committed migration.
    """
    if template_id not in TEMPLATE_DATA_MODELS:
        raise ValueError(f"unknown template: {template_id}")
