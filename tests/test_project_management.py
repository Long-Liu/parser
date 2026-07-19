from decimal import Decimal

import pytest

from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.domain.project import Project
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import ProjectId
from contexts.shared.domain.pagination import Pagination


class FakeProjectRepository:
    def __init__(self):
        self.project = Project(
            ProjectId(1), "P001", "上高项目", contract_price=Decimal("12500"),
            status="normal", progress=Decimal("82"),
        )
        self.list_args = None
        self.deleted = None

    async def find_by_code(self, code):
        return self.project if code == self.project.code else None

    async def find_by_id(self, project_id):
        return self.project if project_id.value == 1 else None

    async def save(self, project):
        if project.id is None:
            project.id = ProjectId(2)
        self.project = project

    async def list_all(self, **kwargs):
        self.list_args = kwargs
        return [self.project], 21

    async def delete(self, project_id):
        self.deleted = project_id.value


class FakeCleanup:
    def __init__(self):
        self.deleted = None

    async def delete_for_project(self, project_id):
        self.deleted = project_id.value


class FakeUsers:
    async def exists(self, user_id):
        return user_id.value == 7


@pytest.mark.asyncio
async def test_project_list_is_filtered_and_paginated():
    repo = FakeProjectRepository()
    result = await ProjectApplicationService(repo).list_all(
        keyword=" 上高 ", status="normal", pagination=Pagination(2, 20, max_size=100),
    )
    assert repo.list_args == {
        "keyword": "上高", "status": "normal", "offset": 20, "limit": 20,
    }
    assert result["pagination"] == {"page": 2, "size": 20, "total": 21}
    assert result["projects"][0]["contract_price"] == 12500.0


@pytest.mark.asyncio
async def test_project_update_and_delete():
    repo = FakeProjectRepository()
    cleanup = FakeCleanup()
    service = ProjectApplicationService(repo, cleanup=cleanup)
    updated = await ProjectApplicationService.update.__wrapped__(
        service, 1, name="新名称", progress=Decimal("90"),
    )
    assert updated["name"] == "新名称"
    assert updated["progress"] == 90.0
    await ProjectApplicationService.delete.__wrapped__(service, 1)
    assert cleanup.deleted == 1
    assert repo.deleted == 1


@pytest.mark.asyncio
async def test_project_assignment_rejects_unknown_user():
    from contexts.shared.domain.exceptions import NotFoundError

    service = ProjectApplicationService(FakeProjectRepository(), users=FakeUsers())
    with pytest.raises(NotFoundError, match="user 99"):
        await ProjectApplicationService.assign_user.__wrapped__(
            service, 1, 99, False, "viewer",
        )


@pytest.mark.asyncio
async def test_project_list_rejects_invalid_pagination():
    with pytest.raises(ValidationError):
        Pagination(0, 20, max_size=100)  # page < 1


class EnrichFakeRepository:
    """Multi-project repo fake for serialization-enrichment tests."""

    def __init__(self, projects):
        self.projects = projects

    async def list_all(self, **kwargs):
        return self.projects, len(self.projects)

    async def find_by_id(self, project_id):
        return next(
            (p for p in self.projects if p.id.value == project_id.value), None
        )


class FakeUsersWithNames:
    def __init__(self, names):
        self.names = names
        self.name_calls = []

    async def exists(self, user_id):
        return True

    async def real_names(self, user_ids):
        self.name_calls.append(list(user_ids))
        return {uid: self.names.get(uid) for uid in user_ids}


class FakeMetrics:
    def __init__(self, data):
        self.data = data
        self.calls = []

    async def latest_gross_profit(self, project_ids):
        self.calls.append(list(project_ids))
        return {pid: self.data[pid] for pid in project_ids if pid in self.data}


def _make_project(pid, manager=None):
    from contexts.shared.domain.identifiers import UserId

    return Project(
        ProjectId(pid), f"P{pid:03d}", f"项目{pid}",
        manager_id=UserId(manager) if manager else None,
    )


@pytest.mark.asyncio
async def test_project_list_enriched_with_manager_name_and_latest_metrics():
    projects = [_make_project(1, manager=7), _make_project(2, manager=8),
                _make_project(3)]
    users = FakeUsersWithNames({7: "张三", 8: "李四"})
    metrics = FakeMetrics({
        1: {"latest_ym": "2025-05", "revenue": 1000.0, "cost": 800.0,
            "profit": 200.0, "profit_rate": 0.2},
    })
    service = ProjectApplicationService(
        EnrichFakeRepository(projects), users=users, metrics=metrics,
    )
    result = await service.list_all(pagination=Pagination(1, 20, max_size=100))
    items = {p["id"]: p for p in result["projects"]}

    # 有批次数据 + 有负责人
    assert items[1]["manager_name"] == "张三"
    assert items[1]["latest_ym"] == "2025-05"
    assert items[1]["revenue"] == 1000.0
    assert items[1]["cost"] == 800.0
    assert items[1]["profit"] == 200.0
    assert items[1]["profit_rate"] == 0.2

    # 有负责人但无批次数据：指标全为 None
    assert items[2]["manager_name"] == "李四"
    assert items[2]["latest_ym"] is None
    assert items[2]["revenue"] is None
    assert items[2]["cost"] is None
    assert items[2]["profit"] is None
    assert items[2]["profit_rate"] is None

    # 无负责人：manager_name 为 None
    assert items[3]["manager_id"] is None
    assert items[3]["manager_name"] is None
    assert items[3]["latest_ym"] is None

    # 批量查询：负责人姓名与经营指标各只查询一次，且一次性传入全部 id
    assert metrics.calls == [[1, 2, 3]]
    assert users.name_calls == [[7, 8]]


@pytest.mark.asyncio
async def test_project_detail_enriched_with_manager_name_and_latest_metrics():
    users = FakeUsersWithNames({7: "张三"})
    metrics = FakeMetrics({
        1: {"latest_ym": "2025-06", "revenue": 2000.0, "cost": 1500.0,
            "profit": 500.0, "profit_rate": 0.25},
    })
    service = ProjectApplicationService(
        EnrichFakeRepository([_make_project(1, manager=7)]),
        users=users, metrics=metrics,
    )
    detail = await service.get_by_id(ProjectId(1))
    assert detail["manager_name"] == "张三"
    assert detail["latest_ym"] == "2025-06"
    assert detail["revenue"] == 2000.0
    assert detail["cost"] == 1500.0
    assert detail["profit"] == 500.0
    assert detail["profit_rate"] == 0.25
    assert metrics.calls == [[1]]
    assert users.name_calls == [[7]]


@pytest.mark.asyncio
async def test_project_enrichment_defaults_to_none_without_providers():
    service = ProjectApplicationService(EnrichFakeRepository([_make_project(1, 7)]))
    item = (await service.list_all(
        pagination=Pagination(1, 20, max_size=100)))["projects"][0]
    assert item["manager_name"] is None
    assert item["latest_ym"] is None
    assert item["revenue"] is None
    assert item["cost"] is None
    assert item["profit"] is None
    assert item["profit_rate"] is None

    detail = await service.get_by_id(ProjectId(1))
    assert detail["manager_name"] is None
    assert detail["latest_ym"] is None
