"""Shared pytest fixtures.

The in-memory Tortoise ``db`` fixture was duplicated verbatim across the
model-backed test modules; it lives here so every test file requests the same
fixture instead of re-defining it.
"""

from __future__ import annotations

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

# noinspection PyProtectedMember
from contexts.shared.infrastructure.database.engine import _MODEL_MODULES


@pytest.fixture
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": list(_MODEL_MODULES)},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()
