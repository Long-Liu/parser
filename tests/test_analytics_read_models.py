"""Repository-level tests for the analytics read model extensions.

Covers: monthly-data full metric groups (sourced from 表11 settlement rows;
rental/target fields have no data source and must be None), cost-details six
calibers, month-comparison MoM changes (including zero-base division), and
multi-project compare 9 metrics + five-dimension scoring boundaries.

Uses an in-memory sqlite database via Tortoise; each test gets a fresh schema.
"""

from decimal import Decimal
from itertools import count

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.analytics.domain.scoring import compare_scores, grade_for
from contexts.analytics.infrastructure.analytics_repository import (
    TortoiseAnalyticsRepository,
)
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.tables import Project
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.pagination import Pagination

# noinspection PyProtectedMember
from contexts.shared.infrastructure.database.engine import _MODEL_MODULES
from contexts.shared.infrastructure.database.tables import (
    SETTLE_CONTRACT_PRICE,
    SETTLE_CUMULATIVE_COST,
    SETTLE_CUMULATIVE_OUTPUT,
    SETTLE_CURRENT_PROFIT,
    SETTLE_CURRENT_PROFIT_RATE,
    SETTLE_FORECAST_COST,
    SETTLE_FORECAST_PROFIT,
    SETTLE_FORECAST_REVENUE,
    DataBudgetLease,
    DataDynamicIndicator,
    DataSettlementOutput,
)


@pytest.fixture
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": list(_MODEL_MODULES)},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


_seq = count(1)


async def make_project(**kwargs) -> Project:
    n = next(_seq)
    defaults = {
        "code": f"P{int(n):04d}",
        "name": f"项目{n}",
        "contract_price": Decimal("1000"),
        "progress": Decimal("80"),
        "status": "normal",
    }
    defaults.update(kwargs)
    return await Project.create(**defaults)


async def make_batch(project_id: int, ym: str, file_name: str = "cost.xlsx") -> UploadBatch:
    return await UploadBatch.create(
        batch_no=f"T{int(next(_seq)):06d}",
        project_id=project_id,
        ym=ym,
        file_name=file_name,
        status="success",
    )


async def make_settlement(batch_id: int, **indicators) -> None:
    """Create 表11 settlement rows: one vertical row per indicator name."""
    for name, value in indicators.items():
        await DataSettlementOutput.create(
            batch_id=batch_id,
            indicator_name=name,
            cumulative_value=Decimal(str(value)),
        )


async def make_indicator(batch_id: int, **kwargs) -> DataDynamicIndicator:
    return await DataDynamicIndicator.create(batch_id=batch_id, **kwargs)


@pytest.mark.asyncio
async def test_dashboard_status_includes_current_profit_rate(db):
    """大屏"项目实时状态"行需要当前毛利率，接口须直接返回（免前端二次拼接）。"""
    project = await make_project()
    batch = await make_batch(project.id, "2026-03")
    await make_settlement(
        batch.id,
        **{
            SETTLE_CURRENT_PROFIT_RATE: "0.148",
            SETTLE_CURRENT_PROFIT: "148",
            SETTLE_CUMULATIVE_OUTPUT: "1000",
        },
    )

    result = await TortoiseAnalyticsRepository().dashboard_status(
        pagination=Pagination(1, 20, max_size=100)
    )

    row = result["projects"][0]
    assert row["id"] == project.id
    assert row["status"] == "normal"
    assert row["progress"] == 80.0
    assert row["profit_rate"] == 14.8  # 0.148 比率 -> 百分数
    assert result["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_dashboard_status_no_batch_keeps_zero_profit_rate(db):
    """无结算数据时 profit_rate 回落为 0.0（与 _profit_item 口径一致）。"""
    await make_project()

    result = await TortoiseAnalyticsRepository().dashboard_status(
        pagination=Pagination(1, 20, max_size=100)
    )

    assert result["projects"][0]["profit_rate"] == 0.0


@pytest.mark.asyncio
async def test_budget_lease_writeoffs_uses_latest_batch_and_aggregates_ui_fields(db):
    project = await make_project(name="资阳项目")
    old_batch = await make_batch(project.id, "2026-02")
    latest_batch = await make_batch(project.id, "2026-03")
    await DataBudgetLease.create(
        batch_id=old_batch.id,
        lease_total=Decimal("999"),
    )
    await DataBudgetLease.create(
        batch_id=latest_batch.id,
        lease_bid=Decimal("100"),
        lease_active=Decimal("200"),
        lease_passive=Decimal("283.19"),
        lease_total=Decimal("583.19"),
        writeoff_total=Decimal("80"),
        remaining_bid=Decimal("20"),
        remaining_active=Decimal("30"),
        remaining_passive=Decimal("40"),
    )

    result = await TortoiseAnalyticsRepository().budget_lease_writeoffs(
        None,
        Pagination(1, 20, max_size=100),
    )

    assert result["pagination"]["total"] == 1
    item = result["projects"][0]
    assert item["project_name"] == "资阳项目"
    assert item["ym"] == "2026-03"
    assert item["budget_lease_total"] == 583.19
    assert item["cumulative_lease"] == {
        "machinery_equipment": 100.0,
        "turnover_materials": 200.0,
        "other": 283.19,
    }
    assert item["written_off_total"] == 80.0
    assert item["unwritten_off_total"] == 503.19
    assert item["remaining_lease"] == {
        "machinery_equipment": 20.0,
        "turnover_materials": 30.0,
        "other": 40.0,
    }
    assert result["summary"]["budget_lease_total"] == 583.19


# ── monthly-data ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_monthly_data_exposes_full_metric_groups(db):
    project = await make_project()
    batch = await make_batch(project.id, "2026-03")
    await make_settlement(
        batch.id,
        **{
            SETTLE_CONTRACT_PRICE: "12500",
            SETTLE_CUMULATIVE_OUTPUT: "12500",
            SETTLE_CUMULATIVE_COST: "10650",
            SETTLE_CURRENT_PROFIT: "1850",
            SETTLE_FORECAST_REVENUE: "12500",
            SETTLE_FORECAST_COST: "10100",
            SETTLE_FORECAST_PROFIT: "2400",
        },
    )
    await make_indicator(
        batch.id,
        display_level="一级显示",
        item_name="项目成本合计",
        indicator_with_tax=Decimal("10000"),
    )
    await DataBudgetLease.create(
        batch_id=batch.id,
        lease_total=Decimal("1200"),
        writeoff_total=Decimal("850"),
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.monthly_data(project.id, Pagination(1, 20, max_size=100))

    assert result["pagination"]["total"] == 1
    item = result["data"][0]
    # legacy fields preserved
    assert item["batch_id"] == batch.id
    assert item["ym"] == "2026-03"
    assert item["file_name"] == "cost.xlsx"
    assert item["status"] == "success"
    assert item["uploaded_at"]
    assert item["revenue"] == 12500.0
    assert item["profit"] == 1850.0
    assert item["cost"] == 10650.0
    assert item["profit_rate"] == 14.8
    # basic group
    assert item["contract_price"] == 12500.0
    assert item["estimated_completion_price"] == 12500.0
    assert item["target_profit"] == 2500.0
    assert item["target_profit_rate"] == 20.0
    # forecast group
    assert item["expected_complete_settlement"] == 12500.0
    assert item["expected_complete_cost"] == 10100.0
    assert item["expected_complete_profit"] == 2400.0
    assert item["expected_complete_profit_rate"] == 19.2
    assert item["rental_expected_settlement"] == 1200.0
    assert item["rental_cost"] == 850.0
    assert item["rental_profit"] == 350.0
    assert item["write_off_rate"] == pytest.approx(70.83)


@pytest.mark.asyncio
async def test_monthly_data_historical_hierarchy_avoids_double_counting(db):
    project = await make_project()
    batch = await make_batch(project.id, "2026-02")
    await make_settlement(batch.id, **{SETTLE_CONTRACT_PRICE: "1000"})
    for hierarchy_code, item_name, amount in (
        ("一", "项目管理费", "300"),
        ("1", "人工费", "100"),
        ("2", "现场管理费", "200"),
        ("二", "建筑工程", "400"),
        ("1", "建筑施工费", "400"),
    ):
        await make_indicator(
            batch.id,
            hierarchy_code=hierarchy_code,
            item_name=item_name,
            indicator_with_tax=Decimal(amount),
        )

    item = (
        await TortoiseAnalyticsRepository().monthly_data(
            project.id,
            Pagination(1, 20, max_size=100),
        )
    )["data"][0]

    assert item["target_profit"] == 300.0
    assert item["target_profit_rate"] == 30.0


@pytest.mark.asyncio
async def test_monthly_data_uses_stored_rate_rows_when_present(db):
    project = await make_project()
    batch = await make_batch(project.id, "2026-03")
    await make_settlement(
        batch.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "12500",
            SETTLE_CURRENT_PROFIT: "1850",
            # rate rows are stored as ratios (0.x) and reported as percents
            SETTLE_CURRENT_PROFIT_RATE: "0.148",
        },
    )

    repo = TortoiseAnalyticsRepository()
    item = (await repo.monthly_data(project.id, Pagination(1, 20, max_size=100)))["data"][0]

    assert item["profit_rate"] == 14.8
    # cumulative cost row missing while other rows exist -> 0 per _settle
    assert item["cost"] == 0.0


@pytest.mark.asyncio
async def test_monthly_data_falls_back_to_contract_price_row(db):
    project = await make_project()
    batch = await make_batch(project.id, "2026-03")
    await make_settlement(
        batch.id,
        **{
            SETTLE_CONTRACT_PRICE: "1100",
            SETTLE_CURRENT_PROFIT: "120",
        },
    )

    repo = TortoiseAnalyticsRepository()
    item = (await repo.monthly_data(project.id, Pagination(1, 20, max_size=100)))["data"][0]

    # 累计结算产值 missing -> revenue falls back to the 合同总价 row
    assert item["revenue"] == 1100.0
    assert item["profit"] == 120.0
    assert item["profit_rate"] == pytest.approx(10.91)


@pytest.mark.asyncio
async def test_monthly_data_without_settlement_rows_returns_zeros(db):
    project = await make_project()
    await make_batch(project.id, "2026-03")

    repo = TortoiseAnalyticsRepository()
    item = (await repo.monthly_data(project.id, Pagination(1, 20, max_size=100)))["data"][0]

    for key in (
        "revenue",
        "cost",
        "profit",
        "profit_rate",
        "contract_price",
        "estimated_completion_price",
        "expected_complete_settlement",
        "expected_complete_cost",
        "expected_complete_profit",
        "expected_complete_profit_rate",
    ):
        assert item[key] == 0.0, key
    # no settlement rows at all -> target/rental groups stay None
    assert item["target_profit"] is None
    assert item["target_profit_rate"] is None
    assert item["rental_expected_settlement"] is None
    assert item["write_off_rate"] is None


# ── cost-details / cost-categories ───────────────────────────────────


@pytest.mark.asyncio
async def test_cost_details_expose_six_calibers_and_hierarchy_code(db):
    project = await make_project()
    batch = await make_batch(project.id, "2026-03")
    await make_indicator(
        batch.id,
        hierarchy_code="1",
        item_name="安装工程",
        indicator_with_tax=Decimal("2230"),
        estimated_with_tax=Decimal("2183"),
        adjusted_with_tax=Decimal("2108"),
        current_budget=Decimal("2032"),
        incurred_cost=Decimal("1710"),
        forecast_with_tax=Decimal("1980"),
    )
    # legacy rows have NULL hierarchy_code and must stay flat without errors
    await make_indicator(
        batch.id,
        hierarchy_code=None,
        item_name="机炉电施工费",
        indicator_with_tax=Decimal("1000"),
        estimated_with_tax=Decimal("980"),
        adjusted_with_tax=Decimal("950"),
        current_budget=Decimal("920"),
        incurred_cost=Decimal("780"),
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.cost_details(project.id, "2026-03", Pagination(1, 20, max_size=100))

    first, second = result["data"]
    assert first["hierarchy_code"] == "1"
    assert first["indicator"] == 2230.0
    assert first["actual"] == 1710.0
    assert first["deviation"] == -520.0
    assert first["deviation_rate"] == pytest.approx(-23.32)
    # new calibers from data_dynamic_indicator
    assert first["list_target"] == 2183.0  # 预计完工量含税指标
    assert first["adj_target"] == 2108.0  # 调整后指标
    assert first["budget"] == 2032.0  # 现执行预算
    assert first["forecast"] == 1980.0

    assert second["hierarchy_code"] is None
    assert second["list_target"] == 980.0
    assert second["adj_target"] == 950.0
    assert second["budget"] == 920.0
    assert second["forecast"] == 980.0


@pytest.mark.asyncio
async def test_cost_categories_report_carries_extended_calibers(db):
    project = await make_project()
    batch = await make_batch(project.id, "2026-03")
    await make_indicator(
        batch.id,
        hierarchy_code="2",
        item_name="其他项目费",
        indicator_with_tax=Decimal("780"),
        estimated_with_tax=Decimal("752"),
        adjusted_with_tax=Decimal("726"),
        current_budget=Decimal("700"),
        incurred_cost=Decimal("600"),
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.cost_categories([project.id], "2026-03", Pagination(1, 20, max_size=100))

    item = result["projects"][0]["items"][0]
    for key in (
        "hierarchy_code",
        "name",
        "indicator",
        "actual",
        "deviation",
        "deviation_rate",
        "list_target",
        "adj_target",
        "budget",
        "forecast",
    ):
        assert key in item, key
    assert item["budget"] == 700.0


# ── month-comparison ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_month_comparison_computes_mom_changes(db):
    project = await make_project()
    for ym, revenue, cost, net in (("2026-02", "100", "90", "10"), ("2026-03", "150", "120", "30")):
        batch = await make_batch(project.id, ym)
        await make_settlement(
            batch.id,
            **{
                SETTLE_CUMULATIVE_OUTPUT: revenue,
                SETTLE_CUMULATIVE_COST: cost,
                SETTLE_CURRENT_PROFIT: net,
            },
        )
        await make_indicator(
            batch.id,
            hierarchy_code="一",
            item_name="项目管理费",
            incurred_cost=Decimal(cost),
            forecast_with_tax=Decimal(f"{Decimal(cost) + Decimal('5')}"),
        )

    repo = TortoiseAnalyticsRepository()
    result = await repo.month_comparison(project.id, ["2026-03", "2026-02"])

    first, second = result["months"]
    assert first["ym"] == "2026-02"
    assert first["mom"] is None  # first selected month has no base period
    assert first["cost_categories"][0] == {
        "hierarchy_code": "一",
        "level": 1,
        "name": "项目管理费",
        "actual": 90.0,
        "forecast": 95.0,
    }

    mom = second["mom"]
    assert mom["revenue"] == {"change": 50.0, "change_pct": 50.0}
    assert mom["cost"] == {"change": 30.0, "change_pct": pytest.approx(33.33)}
    assert mom["profit"] == {"change": 20.0, "change_pct": 200.0}
    # profit_rate expressed in percentage points (pp)
    assert mom["profit_rate"]["change"] == 10.0
    assert mom["profit_rate"]["change_pct"] == 100.0


@pytest.mark.asyncio
async def test_month_comparison_mom_returns_none_when_base_is_zero(db):
    project = await make_project()
    empty = await make_batch(project.id, "2026-01")
    await make_settlement(empty.id, **{SETTLE_CUMULATIVE_OUTPUT: "0", SETTLE_CURRENT_PROFIT: "0"})
    filled = await make_batch(project.id, "2026-02")
    await make_settlement(
        filled.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "100",
            SETTLE_CUMULATIVE_COST: "90",
            SETTLE_CURRENT_PROFIT: "10",
        },
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.month_comparison(project.id, ["2026-01", "2026-02"])

    mom = result["months"][1]["mom"]
    assert mom["revenue"]["change"] == 100.0
    assert mom["revenue"]["change_pct"] is None  # zero base
    assert mom["profit_rate"]["change_pct"] is None


@pytest.mark.asyncio
async def test_month_comparison_requires_two_months(db):
    project = await make_project()
    repo = TortoiseAnalyticsRepository()
    with pytest.raises(ValidationError):
        await repo.month_comparison(project.id, ["2026-01"])


# ── compare ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_projects_returns_metrics_scores_and_legacy_fields(db):
    alpha = await make_project(contract_price=Decimal("12500"), progress=Decimal("82"))
    batch_a = await make_batch(alpha.id, "2026-03")
    await make_settlement(
        batch_a.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "10250",
            SETTLE_CUMULATIVE_COST: "8050",
            SETTLE_CURRENT_PROFIT: "2200",
        },
    )
    beta = await make_project(contract_price=Decimal("8800"), progress=Decimal("75"))
    batch_b = await make_batch(beta.id, "2026-03")
    await make_settlement(
        batch_b.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "6600",
            SETTLE_CUMULATIVE_COST: "5060",
            SETTLE_CURRENT_PROFIT: "1540",
        },
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.compare_projects([alpha.id, beta.id], "2026-03")

    # legacy keys preserved
    assert "cost_categories" in result
    assert "profits" in result

    first, second = result["projects"]
    assert first["project_id"] == alpha.id
    assert first["progress"] == 82.0
    assert first["contract"] == 12500.0
    assert first["settlement"] == 10250.0
    assert first["revenue"] == 10250.0
    assert first["total_cost"] == 8050.0
    assert first["profit"] == 2200.0
    assert first["profit_rate"] == pytest.approx(21.46)
    assert first["settlement_rate"] == 82.0
    assert first["revenue_ratio"] == 100.0
    assert first["unit_cost"] == pytest.approx(78.54)
    assert first["scores"] == {
        "profitability": 90,
        "cost_control": 90,
        "progress_execution": 75,
        "settlement_quality": 74,
        "revenue_conversion": 88,
    }
    assert first["total_score"] == 83.4
    assert first["grade"] == "A"

    assert second["settlement_rate"] == 75.0
    assert second["scores"]["settlement_quality"] == 62
    assert second["scores"]["progress_execution"] == 65
    assert second["total_score"] == 79.0
    assert second["grade"] == "B"


@pytest.mark.asyncio
async def test_compare_profit_rate_boundary_18_scores_90(db):
    alpha = await make_project(contract_price=Decimal("100"))
    batch_a = await make_batch(alpha.id, "2026-03")
    await make_settlement(
        batch_a.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "100",
            SETTLE_CURRENT_PROFIT: "18",
            SETTLE_CUMULATIVE_COST: "82",
        },
    )
    beta = await make_project(contract_price=Decimal("100"))
    batch_b = await make_batch(beta.id, "2026-03")
    await make_settlement(
        batch_b.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "100",
            SETTLE_CURRENT_PROFIT: "17.99",
            SETTLE_CUMULATIVE_COST: "82",
        },
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.compare_projects([alpha.id, beta.id], "2026-03")

    first, second = result["projects"]
    assert first["profit_rate"] == 18.0
    assert first["scores"]["profitability"] == 90
    assert second["profit_rate"] == 17.99
    assert second["scores"]["profitability"] == 75


@pytest.mark.asyncio
async def test_compare_stored_rate_row_preferred_over_computed(db):
    """结算表已存毛利率（比率）时直接采用并换算为百分比。"""
    alpha = await make_project(contract_price=Decimal("100"))
    batch_a = await make_batch(alpha.id, "2026-03")
    await make_settlement(
        batch_a.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "100",
            SETTLE_CURRENT_PROFIT: "18",
            SETTLE_CUMULATIVE_COST: "82",
            SETTLE_CURRENT_PROFIT_RATE: "0.185",
        },
    )
    beta = await make_project(contract_price=Decimal("100"))
    await make_batch(beta.id, "2026-03")

    repo = TortoiseAnalyticsRepository()
    result = await repo.compare_projects([alpha.id, beta.id], "2026-03")

    assert result["projects"][0]["profit_rate"] == 18.5


@pytest.mark.asyncio
async def test_compare_division_by_zero_yields_none_and_lowest_band(db):
    alpha = await make_project(contract_price=Decimal("1000"), progress=Decimal("0"))
    beta = await make_project(contract_price=Decimal("8800"), progress=Decimal("75"))
    batch_b = await make_batch(beta.id, "2026-03")
    await make_settlement(
        batch_b.id,
        **{
            SETTLE_CUMULATIVE_OUTPUT: "6600",
            SETTLE_CUMULATIVE_COST: "5060",
            SETTLE_CURRENT_PROFIT: "1540",
        },
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.compare_projects([alpha.id, beta.id], "2026-03")

    first = result["projects"][0]  # no batch at all -> every ratio undefined/zero
    assert first["settlement"] == 0.0
    assert first["profit_rate"] is None
    assert first["unit_cost"] is None
    assert first["revenue_ratio"] is None
    assert first["settlement_rate"] == 0.0
    assert first["scores"] == {
        "profitability": 40,
        "cost_control": 40,
        "progress_execution": 50,
        "settlement_quality": 45,
        "revenue_conversion": 45,
    }
    assert first["total_score"] == 44.0
    assert first["grade"] == "D"


@pytest.mark.asyncio
async def test_compare_requires_two_projects(db):
    await make_project()
    repo = TortoiseAnalyticsRepository()
    with pytest.raises(ValidationError):
        await repo.compare_projects([1], None)


@pytest.mark.asyncio
async def test_dashboard_health_radar_matches_ui_six_dimensions(db):
    await make_project(progress=Decimal("80"), status="normal")
    dimensions = (await TortoiseAnalyticsRepository().health_radar())["dimensions"]
    assert set(dimensions) == {
        "progress",
        "cost",
        "quality",
        "safety",
        "efficiency",
        "profit",
    }


# ── scoring model boundaries (pure domain) ───────────────────────────


def test_scoring_dimension_boundaries():
    # 盈利能力: >=18 -> 90, >=15 -> 75, >=10 -> 60, else 40, None -> 40
    assert compare_scores(profit_rate=18, unit_cost=82, progress=88, settlement_rate=85, revenue_ratio=94)[
        "scores"
    ] == {
        "profitability": 90,
        "cost_control": 90,
        "progress_execution": 85,
        "settlement_quality": 88,
        "revenue_conversion": 88,
    }
    assert compare_scores(profit_rate=15, unit_cost=86, progress=80, settlement_rate=78, revenue_ratio=90)[
        "scores"
    ] == {
        "profitability": 75,
        "cost_control": 75,
        "progress_execution": 75,
        "settlement_quality": 74,
        "revenue_conversion": 74,
    }
    assert compare_scores(profit_rate=10, unit_cost=90, progress=70, settlement_rate=70, revenue_ratio=85)[
        "scores"
    ] == {
        "profitability": 60,
        "cost_control": 60,
        "progress_execution": 65,
        "settlement_quality": 62,
        "revenue_conversion": 62,
    }
    assert compare_scores(profit_rate=9.99, unit_cost=90.01, progress=69, settlement_rate=69, revenue_ratio=84)[
        "scores"
    ] == {
        "profitability": 40,
        "cost_control": 40,
        "progress_execution": 50,
        "settlement_quality": 45,
        "revenue_conversion": 45,
    }
    # division-by-zero metrics arrive as None -> lowest band per dimension
    assert compare_scores(profit_rate=None, unit_cost=None, progress=None, settlement_rate=None, revenue_ratio=None)[
        "scores"
    ] == {
        "profitability": 40,
        "cost_control": 40,
        "progress_execution": 50,
        "settlement_quality": 45,
        "revenue_conversion": 45,
    }


def test_scoring_total_and_grade_boundaries():
    # total = 83.0 exactly -> A
    scored = compare_scores(profit_rate=18, unit_cost=82, progress=88, settlement_rate=85, revenue_ratio=85)
    assert scored["total_score"] == 83.0
    assert scored["grade"] == "A"
    # total = 79.6 -> B
    scored = compare_scores(profit_rate=18, unit_cost=82, progress=88, settlement_rate=85, revenue_ratio=84.9)
    assert scored["total_score"] == 79.6
    assert scored["grade"] == "B"
    # grade cut-offs 83 / 70 / 58
    assert grade_for(83) == "A"
    assert grade_for(82.99) == "B"
    assert grade_for(70) == "B"
    assert grade_for(69.99) == "C"
    assert grade_for(58) == "C"
    assert grade_for(57.99) == "D"
