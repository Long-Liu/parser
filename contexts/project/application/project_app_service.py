from __future__ import annotations

from contexts.shared.domain.exceptions import ConflictError, NotFoundError
from contexts.shared.domain.identifiers import ProjectId, UserId
from tortoise.transactions import atomic
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository


class ProjectApplicationService:
    def __init__(self, repo: ProjectRepository) -> None:
        self._repo = repo

    @atomic()
    async def create(self, code: str, name: str, created_by: UserId | None = None) -> dict:
        existing = await self._repo.find_by_code(code)
        if existing:
            raise ConflictError("project code already exists")
        project = Project.create(project_id=None, code=code, name=name,
                                 created_by=created_by)
        await self._repo.save(project)
        if project.id is None:
            raise RuntimeError("project repository did not assign an id")
        return {"id": project.id.value, "code": project.code, "name": project.name}

    async def list_all(self) -> list[dict]:
        projects = await self._repo.list_all()
        return [{"id": p.id.value, "code": p.code, "name": p.name} for p in projects]

    async def get_by_id(self, project_id: ProjectId) -> dict:
        p = await self._repo.find_by_id(project_id)
        if not p:
            raise NotFoundError(f"project {project_id} not found")
        return {"id": p.id.value, "code": p.code, "name": p.name}

    @atomic()
    async def assign_user(self, project_id: int, user_id: int, is_primary: bool = False) -> None:
        if await self._repo.find_by_id(ProjectId(project_id)) is None:
            raise NotFoundError(f"project {project_id} not found")
        await self._repo.assign_user(ProjectId(project_id), UserId(user_id), is_primary)

    @atomic()
    async def remove_user(self, project_id: int, user_id: int) -> None:
        await self._repo.remove_user(ProjectId(project_id), UserId(user_id))
