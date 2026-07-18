"""Alert metric provider must not fabricate gross_profit_rate.

The 毛利 sheet was retired from the import format, so new batches have no
data_gross_profit rows. TortoiseAlertMetricProvider.snapshot() must then omit
the gross_profit_rate metric entirely (rules skip missing metrics) instead of
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


def _patch_models(monkeypatch, *, gross_row, indicator_rows=()):
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
        alert_repositories.DataGrossProfit, "filter", lambda **kw: _FakeQuery(gross_row)
    )
    monkeypatch.setattr(
        alert_repositories.DataDynamicIndicator,
        "filter",
        lambda **kw: _FakeQuery(list(indicator_rows)),
    )


@pytest.mark.asyncio
async def test_snapshot_omits_gross_profit_rate_when_no_rows(monkeypatch):
    _patch_models(monkeypatch, gross_row=None)

    ym, metrics = await TortoiseAlertMetricProvider().snapshot(1, "2026-07")

    assert ym == "2026-07"
    assert "gross_profit_rate" not in metrics
    assert metrics["cost_deviation_rate"] == Decimal("0")
    assert metrics["manual_warning"] == Decimal("0")


@pytest.mark.asyncio
async def test_snapshot_computes_gross_profit_rate_when_row_exists(monkeypatch):
    gross = SimpleNamespace(
        actual_revenue=Decimal("200"), contract_price=None,
        actual_profit=Decimal("20"), gross_profit_net=None,
    )
    _patch_models(monkeypatch, gross_row=gross)

    _, metrics = await TortoiseAlertMetricProvider().snapshot(1, "2026-07")

    assert metrics["gross_profit_rate"] == Decimal("10")
