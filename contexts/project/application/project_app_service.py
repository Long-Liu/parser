from __future__ import annotations

from collections.abc import Callable

from contexts.shared.domain.exceptions import ConflictError, NotFoundError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.unit_of_work import UnitOfWork
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository


class ProjectApplicationService:
    def __init__(self, repo: ProjectRepository, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._repo = repo
        self._uow_factory = uow_factory

    async def create(self, code: str, name: str, created_by: UserId | None = None) -> dict:
        existing = await self._repo.find_by_code(code)
        if existing:
            raise ConflictError("project code already exists")
        project = Project.create(project_id=None, code=code, name=name,
                                 created_by=created_by)
        async with self._uow_factory() as uow:
            await self._repo.save(project)
            await uow.commit()
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
