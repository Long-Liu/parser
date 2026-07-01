"""Project service."""

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from repositories.project_repository import ProjectRepo
from services.errors_service import ConflictError, ServiceError


def _serialize_project(project: dict) -> dict:
    data = dict(project)
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat(sep=" ")
    return data


async def list_projects(page: int = 1, size: int = 20) -> dict:
    offset = (page - 1) * size
    rows = await ProjectRepo.list_page(limit=size, offset=offset)
    return {
        "total": await ProjectRepo.count(),
        "page": page,
        "size": size,
        "projects": [_serialize_project(row) for row in rows],
    }


async def get_project(project_id: int) -> dict | None:
    project = await ProjectRepo.get_by_id(project_id)
    return _serialize_project(project) if project else None


async def create_project(code: str, name: str, user_id: int) -> dict:
    existing = await ProjectRepo.get_by_code(code)
    if existing:
        raise ConflictError("project code already exists")

    try:
        pid = await ProjectRepo.insert(code=code, name=name, created_by=user_id)
    except IntegrityError:
        raise ConflictError("project code already exists") from None
    project = await get_project(pid)
    return project or {"id": pid, "code": code, "name": name, "created_by": user_id}


async def update_project(project_id: int, *, code: str | None = None,
                         name: str | None = None) -> dict:
    project = await ProjectRepo.get_by_id(project_id)
    if not project:
        raise ServiceError("not found", http_status=404)

    values = {}
    if code is not None:
        existing = await ProjectRepo.get_by_code(code)
        if existing and existing["id"] != project_id:
            raise ConflictError("project code already exists")
        values["code"] = code
    if name is not None:
        values["name"] = name

    if not values:
        raise ServiceError("code or name is required", http_status=400)

    try:
        await ProjectRepo.update_by_id(project_id, **values)
    except IntegrityError:
        raise ConflictError("project code already exists") from None
    updated = await get_project(project_id)
    if updated is None:
        raise ServiceError("not found", http_status=404)
    return updated


async def delete_project(project_id: int) -> None:
    project = await ProjectRepo.get_by_id(project_id)
    if not project:
        raise ServiceError("not found", http_status=404)
    try:
        await ProjectRepo.delete_by_id(project_id)
    except IntegrityError:
        raise ConflictError("project is in use") from None
