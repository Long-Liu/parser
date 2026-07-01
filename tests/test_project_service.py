from datetime import datetime

import pytest

from services.errors_service import ConflictError, ServiceError
from services.project_service import create_project, delete_project, list_projects, update_project


@pytest.mark.asyncio
async def test_list_projects_returns_paginated_result(monkeypatch):
    calls = {}

    async def fake_list_page(*, limit=None, offset=None):
        calls["limit"] = limit
        calls["offset"] = offset
        return [{
            "id": 2,
            "code": "P002",
            "name": "Project 2",
            "created_at": datetime(2026, 7, 1, 9, 30),
        }]

    async def fake_count(*where):
        return 11

    from repositories.project_repository import ProjectRepo
    monkeypatch.setattr(ProjectRepo, "list_page", fake_list_page)
    monkeypatch.setattr(ProjectRepo, "count", fake_count)

    result = await list_projects(page=2, size=10)

    assert calls == {"limit": 10, "offset": 10}
    assert result["total"] == 11
    assert result["page"] == 2
    assert result["size"] == 10
    assert result["projects"][0]["created_at"] == "2026-07-01 09:30:00"


@pytest.mark.asyncio
async def test_create_project_rejects_duplicate_code(monkeypatch):
    from repositories.project_repository import ProjectRepo

    async def fake_get_by_code(code):
        return {"id": 1, "code": "P001"}

    monkeypatch.setattr(ProjectRepo, "get_by_code", fake_get_by_code)

    with pytest.raises(ConflictError):
        await create_project(code="P001", name="Project 1", user_id=1)


@pytest.mark.asyncio
async def test_update_project_rejects_empty_payload(monkeypatch):
    from repositories.project_repository import ProjectRepo

    async def fake_get_by_id(project_id):
        return {"id": 1, "code": "P001", "name": "Project 1"}

    monkeypatch.setattr(ProjectRepo, "get_by_id", fake_get_by_id)

    with pytest.raises(ServiceError) as exc:
        await update_project(1)

    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_delete_project_returns_404_when_missing(monkeypatch):
    from repositories.project_repository import ProjectRepo

    async def fake_get_by_id(project_id):
        return None

    monkeypatch.setattr(ProjectRepo, "get_by_id", fake_get_by_id)

    with pytest.raises(ServiceError) as exc:
        await delete_project(1)

    assert exc.value.http_status == 404
