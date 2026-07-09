from __future__ import annotations

from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository
from contexts.project.infrastructure.tables import Project as OrmProject
from contexts.shared.domain.identifiers import ProjectId, UserId


def _to_entity(orm: OrmProject) -> Project:
    return Project(
        project_id=ProjectId(orm.id),
        code=orm.code,
        name=orm.name,
        created_by=UserId(orm.created_by) if orm.created_by else None,
    )


class ProjectRepositoryImpl(ProjectRepository):
    async def save(self, project: Project) -> None:
        values = {
            "code": project.code,
            "name": project.name,
            "created_by": project.created_by.value if project.created_by else None,
        }
        if project.id is None:
            orm = await OrmProject.create(**values)
            project.id = ProjectId(orm.id)
            return
        existing = await OrmProject.get_or_none(id=project.id.value)
        if existing is None:
            orm = OrmProject(id=project.id.value, **values)
            await orm.save(force_create=True)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            await existing.save(update_fields=list(values.keys()))

    async def find_by_id(self, project_id: ProjectId) -> Project | None:
        orm = await OrmProject.get_or_none(id=project_id.value)
        return _to_entity(orm) if orm else None

    async def find_by_code(self, code: str) -> Project | None:
        orm = await OrmProject.get_or_none(code=code)
        return _to_entity(orm) if orm else None

    async def list_all(self) -> list[Project]:
        return [_to_entity(o) for o in await OrmProject.all()]
