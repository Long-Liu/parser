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
