"""Analytics gross-profit figures come from the settlement output sheet.

After the 毛利 sheet was retired and data_gross_profit dropped, the
project_profits report, monthly items and per-project profit lookups read
表11 结算产值表 (data_settlement_output) vertical indicator rows instead.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from contexts.analytics.infrastructure import analytics_repository as analytics
from contexts.analytics.infrastructure.analytics_repository import (
    TortoiseAnalyticsRepository,
)
from contexts.shared.domain.pagination import Pagination


class _FakeQuery:
    """Minimal stand-in for the Tortoise queryset chains used in analytics."""

    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    async def count(self):
        return len(self._rows)

    async def first(self):
        return self._rows[0] if self._rows else None

    def __await__(self):
        async def _resolve():
            return list(self._rows)

        return _resolve().__await__()


def _row(name, value):
    return SimpleNamespace(
        batch_id=7, indicator_name=name,
        cumulative_value=None if value is None else Decimal(str(value)),
    )


SETTLEMENT_ROWS = [
    _row("合同总价", "66075.19"),
    _row("累计结算产值", "110331.738327"),
    _row("预计完工收入", "24793.025889"),
    _row("累计发生总成本", "3615.323276"),
    _row("预计完工成本", "22140.962109"),
    _row("截至当期毛利", "106716.415051"),
    _row("截至当期毛利率", "0"),
    _row("预计毛利", "2652.063780"),
    _row("预计毛利率", "0.106968"),
]


def _batch():
    return SimpleNamespace(
        id=7, project_id=1, ym="2026-07", status="success",
        file_name="wb.xlsx", created_at=datetime(2026, 7, 14, 10, 0, 0),
    )


def _project(**overrides):
    values = dict(id=1, code="DY-A", name="电源A项目", status="normal",
                  progress=Decimal("0"), contract_price=Decimal("66075.19"))
    values.update(overrides)
    return SimpleNamespace(**values)


def _dyn_row(estimated, indicator=None):
    """00 动态指标 sheet row: 预计完工量含税指标 / 清单量含税指标."""
    return SimpleNamespace(
        batch_id=7,
        estimated_with_tax=None if estimated is None else Decimal(str(estimated)),
        indicator_with_tax=None if indicator is None else Decimal(str(indicator)),
    )


def _patch(monkeypatch, *, settlement_rows=SETTLEMENT_ROWS, dynamic_rows=(),
           project=None, batch=None):
    project = project or _project()
    batch = _batch() if batch is None else batch
    monkeypatch.setattr(analytics.Project, "all", lambda: _FakeQuery([project]))
    monkeypatch.setattr(
        analytics.UploadBatch, "filter", lambda **kw: _FakeQuery([batch] if batch else [])
    )
    monkeypatch.setattr(
        analytics.DataSettlementOutput, "filter",
        lambda **kw: _FakeQuery(settlement_rows),
    )
    monkeypatch.setattr(
        analytics.DataDynamicIndicator, "filter",
        lambda **kw: _FakeQuery(list(dynamic_rows)),
    )


@pytest.mark.asyncio
async def test_project_profits_reads_settlement_indicators(monkeypatch):
    _patch(monkeypatch)

    result = await TortoiseAnalyticsRepository().project_profits(
        None, Pagination(1, 20, max_size=100))

    item = result["projects"][0]
    assert item["ym"] == "2026-07"
    current = item["current"]
    assert current["revenue"] == pytest.approx(110331.738327)
    assert current["profit"] == pytest.approx(106716.415051)
    assert current["cost"] == pytest.approx(3615.323276)
    # stored ratio 0 -> percent 0
    assert current["profit_rate"] == 0.0
    forecast = item["forecast"]
    assert forecast["revenue"] == pytest.approx(24793.025889)
    assert forecast["profit"] == pytest.approx(2652.063780)
    assert forecast["cost"] == pytest.approx(22140.962109)
    # stored ratio 0.106968 -> percent 10.7
    assert forecast["profit_rate"] == pytest.approx(10.7)
    # no bid split exists in the workbook; indicator needs 动态指标 rows
    assert item["bid"] == {"revenue": 0.0, "cost": 0.0, "profit": 0.0,
                           "profit_rate": 0.0}
    assert item["indicator"] == {"revenue": 0.0, "cost": 0.0, "profit": 0.0,
                                 "profit_rate": 0.0}


@pytest.mark.asyncio
async def test_project_profits_indicator_reads_dynamic_indicator_sheet(monkeypatch):
    """指标（含税）口径来自 00 动态指标 sheet：预计完工成本取预计完工量
    含税指标合计，收入以表11 合同总价近似。"""
    _patch(monkeypatch, dynamic_rows=[
        _dyn_row(estimated="63361", indicator="64555.20"),
        _dyn_row(estimated="1000"),
    ])

    result = await TortoiseAnalyticsRepository().project_profits(
        None, Pagination(1, 20, max_size=100))

    indicator = result["projects"][0]["indicator"]
    assert indicator["revenue"] == pytest.approx(66075.19)   # 合同总价
    assert indicator["cost"] == pytest.approx(64361.0)       # 63361 + 1000
    assert indicator["profit"] == pytest.approx(1714.19)     # 66075.19 - 64361
    assert indicator["profit_rate"] == pytest.approx(2.59)   # 1714.19/66075.19


@pytest.mark.asyncio
async def test_project_profits_indicator_falls_back_to_list_indicator(monkeypatch):
    """预计完工量含税指标缺失时回退清单量含税指标；无结算行时收入回退
    项目合同价。"""
    _patch(monkeypatch, settlement_rows=[], dynamic_rows=[
        _dyn_row(estimated=None, indicator="60000"),
        _dyn_row(estimated=None, indicator=None),  # 无数据行不计入
    ])

    result = await TortoiseAnalyticsRepository().project_profits(
        None, Pagination(1, 20, max_size=100))

    indicator = result["projects"][0]["indicator"]
    assert indicator["revenue"] == pytest.approx(66075.19)  # project contract price
    assert indicator["cost"] == pytest.approx(60000.0)
    assert indicator["profit"] == pytest.approx(6075.19)
    assert indicator["profit_rate"] == pytest.approx(9.19)


@pytest.mark.asyncio
async def test_project_profits_without_settlement_rows_falls_back(monkeypatch):
    _patch(monkeypatch, settlement_rows=[])

    result = await TortoiseAnalyticsRepository().project_profits(
        None, Pagination(1, 20, max_size=100))

    current = result["projects"][0]["current"]
    assert current["revenue"] == pytest.approx(66075.19)  # project contract price
    assert current["profit"] == 0.0
    assert current["profit_rate"] == 0.0


@pytest.mark.asyncio
async def test_monthly_item_reads_settlement_indicators(monkeypatch):
    monkeypatch.setattr(
        analytics.DataSettlementOutput, "filter",
        lambda **kw: _FakeQuery(SETTLEMENT_ROWS),
    )

    item = await TortoiseAnalyticsRepository()._monthly_item(_batch())

    assert item["revenue"] == pytest.approx(110331.738327)
    assert item["profit"] == pytest.approx(106716.415051)
    assert item["cost"] == pytest.approx(3615.323276)
    assert item["profit_rate"] == 0.0


@pytest.mark.asyncio
async def test_profit_for_reads_settlement_indicators(monkeypatch):
    _patch(monkeypatch)

    profit = await TortoiseAnalyticsRepository()._profit_for(1, None)

    assert profit["ym"] == "2026-07"
    assert profit["profit"] == pytest.approx(106716.415051)
    assert profit["profit_rate"] == 0.0
