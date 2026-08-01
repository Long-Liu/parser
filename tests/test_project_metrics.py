"""Regression tests for TortoiseProjectMetrics.latest_gross_profit.

The latest month per project must be resolved via SQL aggregation — only
newest-month batches are loaded instead of every historical batch."""

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.repositories import TortoiseProjectMetrics
from contexts.shared.infrastructure.database.tables import (
    SETTLE_CUMULATIVE_OUTPUT,
    SETTLE_CURRENT_PROFIT,
    SETTLE_CURRENT_PROFIT_RATE,
    DataSettlementOutput,
)

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


async def test_latest_gross_profit_picks_newest_month_per_project(db):
    # Project 1: two successful batches (older + newest month).
    await UploadBatch.create(id=1, batch_no="B1", project_id=1, ym="2026-05", status="success")
    await UploadBatch.create(id=2, batch_no="B2", project_id=1, ym="2026-07", status="success")
    # Project 2: a single successful batch in an older month.
    await UploadBatch.create(id=3, batch_no="B3", project_id=2, ym="2026-06", status="success")
    # Non-success batch in a newer month must be ignored.
    await UploadBatch.create(id=4, batch_no="B4", project_id=1, ym="2026-08", status="partial")

    # Indicators on the newest batches (id 2 for project 1, id 3 for project 2).
    await DataSettlementOutput.create(
        batch_id=2, indicator_name=SETTLE_CUMULATIVE_OUTPUT, cumulative_value="1000"
    )
    await DataSettlementOutput.create(
        batch_id=2, indicator_name=SETTLE_CURRENT_PROFIT, cumulative_value="150"
    )
    await DataSettlementOutput.create(
        batch_id=2, indicator_name=SETTLE_CURRENT_PROFIT_RATE, cumulative_value="0.15"
    )
    await DataSettlementOutput.create(
        batch_id=3, indicator_name=SETTLE_CUMULATIVE_OUTPUT, cumulative_value="500"
    )

    result = await TortoiseProjectMetrics().latest_gross_profit([1, 2])

    assert set(result) == {1, 2}
    assert result[1]["latest_ym"] == "2026-07"
    assert result[1]["revenue"] == 1000.0
    assert result[1]["profit"] == 150.0
    assert result[2]["latest_ym"] == "2026-06"
    assert result[2]["revenue"] == 500.0


async def test_latest_gross_profit_returns_empty_for_missing(db):
    assert await TortoiseProjectMetrics().latest_gross_profit([99]) == {}
    assert await TortoiseProjectMetrics().latest_gross_profit([]) == {}
