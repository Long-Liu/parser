"""Tests for hierarchy path resolution in the cost-categories read model.

Raw parse-time codes restart numbering under each Chinese-numeral top-level
group, so the analytics read model rewrites them to globally-unique full
paths ("二.2.1") and attaches a 1-based ``level``. Covers the pure resolver
state machine and the repository integration (resolution before pagination,
garbage NULL-name rows excluded).
"""

from decimal import Decimal
from itertools import count

import pytest
from tortoise import Tortoise

from contexts.analytics.domain.hierarchy import resolve_hierarchy_paths
from contexts.analytics.infrastructure.analytics_repository import (
    TortoiseAnalyticsRepository,
)
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.tables import Project
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.database.engine import _MODEL_MODULES
from contexts.shared.infrastructure.database.tables import DataDynamicIndicator


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


async def make_project() -> Project:
    n = next(_seq)
    return await Project.create(
        code=f"H{n:04d}", name=f"层级项目{n}",
        contract_price=Decimal("1000"), progress=Decimal("50"),
        status="normal",
    )


async def make_batch(project_id: int, ym: str = "2026-07") -> UploadBatch:
    return await UploadBatch.create(
        batch_no=f"H{next(_seq):06d}", project_id=project_id, ym=ym,
        file_name="cost.xlsx", status="success",
    )


# ── pure resolver ────────────────────────────────────────────────────


def test_chinese_sections_restart_numbering_become_unique_paths():
    items = [
        {"hierarchy_code": "一", "name": "项目管理费"},
        {"hierarchy_code": "1", "name": "人工费"},
        {"hierarchy_code": "1.1", "name": "基本人工费"},
        {"hierarchy_code": "二", "name": "建筑工程"},
        {"hierarchy_code": "1", "name": "建筑施工费"},
        {"hierarchy_code": "1.1", "name": "土方"},
        {"hierarchy_code": "2.1", "name": "混凝土"},
    ]
    resolve_hierarchy_paths(items)

    assert [i["hierarchy_code"] for i in items] == [
        "一", "一.1", "一.1.1", "二", "二.1", "二.1.1", "二.2.1",
    ]
    assert [i["level"] for i in items] == [1, 2, 3, 1, 2, 3, 3]
    codes = [i["hierarchy_code"] for i in items]
    assert len(set(codes)) == len(codes), "全路径码必须全局唯一"


def test_sheet_without_chinese_numerals_keeps_plain_levels():
    items = [
        {"hierarchy_code": "1", "name": "a"},
        {"hierarchy_code": "1.1", "name": "b"},
        {"hierarchy_code": "2", "name": "c"},
    ]
    resolve_hierarchy_paths(items)

    assert [i["hierarchy_code"] for i in items] == ["1", "1.1", "2"]
    assert [i["level"] for i in items] == [1, 2, 1]


def test_rows_without_code_stay_flat_and_do_not_reset_section():
    items = [
        {"hierarchy_code": "七", "name": "项目成本合计"},
        {"hierarchy_code": None, "name": "其中：安全文明施工费"},
        {"hierarchy_code": "八", "name": "主合同价"},
        {"hierarchy_code": "1", "name": "建筑工程分部分项工程"},
    ]
    resolve_hierarchy_paths(items)

    assert items[1]["hierarchy_code"] is None
    assert items[1]["level"] is None
    # 无码行不中断状态机：八 之后的 1 仍挂到 八 下
    assert items[3]["hierarchy_code"] == "八.1"
    assert items[3]["level"] == 2


# ── repository integration ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_cost_categories_returns_full_paths_and_levels(db):
    project = await make_project()
    batch = await make_batch(project.id)
    rows = [
        ("一", "项目管理费"), ("1", "人工费"), ("1.1", "基本人工费"),
        ("二", "建筑工程"), ("1", "建筑施工费"), ("2.1", "混凝土"),
        (None, "其中：安全文明施工费"),
    ]
    for code, name in rows:
        await DataDynamicIndicator.create(
            batch_id=batch.id, hierarchy_code=code, item_name=name,
            indicator_with_tax=Decimal("100"), incurred_cost=Decimal("90"),
        )

    repo = TortoiseAnalyticsRepository()
    result = await repo.cost_categories([project.id], "2026-07",
                                        Pagination(1, 20, max_size=100))
    items = result["projects"][0]["items"]

    assert [(i["hierarchy_code"], i["level"]) for i in items] == [
        ("一", 1), ("一.1", 2), ("一.1.1", 3),
        ("二", 1), ("二.1", 2), ("二.2.1", 3),
        (None, None),
    ]


@pytest.mark.asyncio
async def test_hierarchy_resolved_before_pagination_slice(db):
    """分页切片发生在路径解析之后：第二页的行仍携带完整全路径。"""
    project = await make_project()
    batch = await make_batch(project.id)
    rows = [
        ("一", "项目管理费"), ("1", "人工费"),
        ("二", "建筑工程"), ("1", "建筑施工费"), ("1.1", "土方"),
    ]
    for code, name in rows:
        await DataDynamicIndicator.create(
            batch_id=batch.id, hierarchy_code=code, item_name=name,
            indicator_with_tax=Decimal("100"), incurred_cost=Decimal("90"),
        )

    repo = TortoiseAnalyticsRepository()
    page2 = await repo.cost_categories([project.id], "2026-07",
                                       Pagination(2, 2, max_size=100))
    items = page2["projects"][0]["items"]

    assert [(i["hierarchy_code"], i["level"]) for i in items] == [
        ("二", 1), ("二.1", 2),
    ]
    assert page2["pagination"]["total"] == 5


@pytest.mark.asyncio
async def test_null_name_garbage_rows_are_excluded(db):
    project = await make_project()
    batch = await make_batch(project.id)
    await DataDynamicIndicator.create(
        batch_id=batch.id, hierarchy_code="一", item_name="项目管理费",
        indicator_with_tax=Decimal("100"), incurred_cost=Decimal("90"),
    )
    # 解析尾行产生的无名垃圾行不应进入报表
    await DataDynamicIndicator.create(
        batch_id=batch.id, hierarchy_code=None, item_name=None,
    )

    repo = TortoiseAnalyticsRepository()
    result = await repo.cost_categories([project.id], "2026-07",
                                        Pagination(1, 20, max_size=100))

    assert result["pagination"]["total"] == 1
    items = result["projects"][0]["items"]
    assert len(items) == 1
    assert items[0]["name"] == "项目管理费"
