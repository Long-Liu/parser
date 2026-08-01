"""Regression tests for alert summary aggregation (one GROUP BY instead of
five COUNT queries)."""

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.alert.infrastructure.repositories import TortoiseAlertRepository
from contexts.alert.infrastructure.tables import AlertModel

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


async def _seed_alerts() -> None:
    await AlertModel.create(
        project_id=1, rule_code="R1", alert_type="cost", level="critical",
        title="a", message="m", metric_value="10", threshold_value="20",
        fingerprint="1:R1", status="active",
        first_triggered_at="2026-07-01T00:00:00", last_triggered_at="2026-07-01T00:00:00",
    )
    await AlertModel.create(
        project_id=1, rule_code="R2", alert_type="cost", level="warning",
        title="b", message="m", metric_value="10", threshold_value="20",
        fingerprint="1:R2", status="acknowledged",
        first_triggered_at="2026-07-01T00:00:00", last_triggered_at="2026-07-01T00:00:00",
    )
    await AlertModel.create(
        project_id=1, rule_code="R3", alert_type="cost", level="warning",
        title="c", message="m", metric_value="10", threshold_value="20",
        fingerprint="1:R3", status="resolved",  # excluded from open summary
        first_triggered_at="2026-07-01T00:00:00", last_triggered_at="2026-07-01T00:00:00",
    )
    await AlertModel.create(
        project_id=2, rule_code="R4", alert_type="cost", level="critical",
        title="d", message="m", metric_value="10", threshold_value="20",
        fingerprint="2:R4", status="active",
        first_triggered_at="2026-07-01T00:00:00", last_triggered_at="2026-07-01T00:00:00",
    )


async def test_summary_aggregates_open_alerts(db):
    await _seed_alerts()
    repo = TortoiseAlertRepository()

    result = await repo.summary(None)
    assert result == {
        "total": 3,
        "active": 2,
        "acknowledged": 1,
        "critical": 2,
        "warning": 1,
    }


async def test_summary_respects_project_filter(db):
    await _seed_alerts()
    repo = TortoiseAlertRepository()

    result = await repo.summary([1])
    assert result == {"total": 2, "active": 1, "acknowledged": 1, "critical": 1, "warning": 1}


async def test_summary_empty(db):
    repo = TortoiseAlertRepository()
    assert await repo.summary(None) == {
        "total": 0,
        "active": 0,
        "acknowledged": 0,
        "critical": 0,
        "warning": 0,
    }
