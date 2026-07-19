"""Alert metric provider reads gross_profit_rate from the settlement sheet.

The 毛利 sheet was retired and data_gross_profit dropped. Gross-profit
reporting now comes from 表11 结算产值表 (data_settlement_output): the
「截至当期毛利率」 row holds a ratio (0.x) which snapshot() converts to a
percent for the GROSS_PROFIT_LOW rule. When that indicator row is missing
the metric must be omitted entirely (rules skip missing metrics) instead of
emitting a fabricated default.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from contexts.alert.infrastructure import repositories as alert_repositories
from contexts.alert.infrastructure.repositories import TortoiseAlertMetricProvider


class _FakeQuery:
    """Minimal stand-in for the Tortoise queryset chains used in snapshot()."""

    def __init__(self, result):
        self._result = result

    def filter(self, **kwargs):
        return self

    def order_by(self, *args):
        return self

    async def first(self):
        return self._result

    def __await__(self):
        async def _resolve():
            return self._result

        return _resolve().__await__()


def _settlement_row(name, value):
    return SimpleNamespace(indicator_name=name, cumulative_value=value)


def _patch_models(monkeypatch, *, settlement_rows=(), indicator_rows=()):
    project = SimpleNamespace(
        id=1, status="normal", progress=0, start_date=None, end_date=None,
    )
    batch = SimpleNamespace(id=7, ym="2026-07")
    monkeypatch.setattr(
        alert_repositories.Project, "get_or_none", AsyncMock(return_value=project)
    )
    monkeypatch.setattr(
        alert_repositories.UploadBatch, "filter", lambda **kw: _FakeQuery(batch)
    )
    monkeypatch.setattr(
        alert_repositories.DataSettlementOutput,
        "filter",
        lambda **kw: _FakeQuery(list(settlement_rows)),
    )
    monkeypatch.setattr(
        alert_repositories.DataDynamicIndicator,
        "filter",
        lambda **kw: _FakeQuery(list(indicator_rows)),
    )


@pytest.mark.asyncio
async def test_snapshot_omits_gross_profit_rate_when_no_settlement_rows(monkeypatch):
    _patch_models(monkeypatch)

    ym, metrics = await TortoiseAlertMetricProvider().snapshot(1, "2026-07")

    assert ym == "2026-07"
    assert "gross_profit_rate" not in metrics
    assert metrics["cost_deviation_rate"] == Decimal("0")
    assert metrics["manual_warning"] == Decimal("0")


@pytest.mark.asyncio
async def test_snapshot_omits_gross_profit_rate_when_rate_row_missing(monkeypatch):
    _patch_models(monkeypatch, settlement_rows=[
        _settlement_row("截至当期毛利", Decimal("106716.415051")),
    ])

    _, metrics = await TortoiseAlertMetricProvider().snapshot(1, "2026-07")

    assert "gross_profit_rate" not in metrics


@pytest.mark.asyncio
async def test_snapshot_converts_settlement_rate_to_percent(monkeypatch):
    _patch_models(monkeypatch, settlement_rows=[
        _settlement_row("截至当期毛利率", Decimal("0.106968")),
    ])

    _, metrics = await TortoiseAlertMetricProvider().snapshot(1, "2026-07")

    assert metrics["gross_profit_rate"] == Decimal("0.106968") * 100
