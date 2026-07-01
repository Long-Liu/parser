from __future__ import annotations

from contexts.shared.domain.exceptions import ConflictError, NotFoundError, ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository


class ProjectApplicationService:
    def __init__(self, repo: ProjectRepository) -> None:
        self._repo = repo

    async def create(self, code: str, name: str, created_by: int | None = None) -> dict:
        if not code or not name:
            raise ValidationError("code and name are required")
        existing = await self._repo.find_by_code(code)
        if existing:
            raise ConflictError("project code already exists")
        project = Project.create(project_id=ProjectId(0), code=code, name=name,
                                 created_by=UserId(created_by) if created_by else None)
        async with SqlAlchemyUnitOfWork() as uow:
            await self._repo.save(project)
            await uow.commit()
        return {"id": project.id.value, "code": project.code, "name": project.name}

    async def list_all(self) -> list[dict]:
        projects = await self._repo.list_all()
        return [{"id": p.id.value, "code": p.code, "name": p.name} for p in projects]

    async def get_by_id(self, project_id: int) -> dict:
        p = await self._repo.find_by_id(ProjectId(project_id))
        if not p:
            raise NotFoundError(f"project {project_id} not found")
        return {"id": p.id.value, "code": p.code, "name": p.name}
