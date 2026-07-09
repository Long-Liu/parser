from __future__ import annotations

# DDL helpers for Tortoise models.

from tortoise import Tortoise

from contexts.shared.infrastructure.database.engine import ensure_initialized
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS


async def init_db():
    """Create all registered Tortoise tables if they don't exist."""
    ensure_initialized()
    await Tortoise.generate_schemas(safe=True)


async def create_data_table(template_id: str):
    """Validate that a template data table model is registered.

    ``init_db`` creates all registered Tortoise models in one pass. This hook is
    kept for the existing bootstrap flow and to fail fast on unknown templates.
    """
    if template_id not in TEMPLATE_DATA_MODELS:
        raise ValueError(f"unknown template: {template_id}")
