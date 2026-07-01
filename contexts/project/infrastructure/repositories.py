from __future__ import annotations

import sqlalchemy as sa

from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.models import Project as OrmProject
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository


def _to_entity(orm: OrmProject) -> Project:
    return Project(project_id=ProjectId(orm.id), code=orm.code, name=orm.name,
                   created_by=UserId(orm.created_by) if orm.created_by else None)


class ProjectRepositoryImpl(ProjectRepository):
    async def save(self, project: Project) -> None:
        async def _save(session):
            values = {
                "code": project.code,
                "name": project.name,
                "created_by": project.created_by.value if project.created_by else None,
            }
            if project.id is None:
                orm = OrmProject(**values)
                session.add(orm)
                await session.flush()
                project.id = ProjectId(orm.id)
                return
            existing = await session.execute(
                sa.select(OrmProject.id).where(OrmProject.id == project.id.value)
            )
            if existing.first() is None:
                session.add(OrmProject(id=project.id.value, **values))
            else:
                await session.execute(
                    sa.update(OrmProject)
                    .where(OrmProject.id == project.id.value)
                    .values(**values)
                )
            await session.flush()

        session = current_session()
        if session is not None:
            await _save(session)
        else:
            async with get_sessionmaker().begin() as s:
                await _save(s)

    async def find_by_id(self, project_id: ProjectId) -> Project | None:
        async def _find(s):
            result = await s.execute(sa.select(OrmProject).where(OrmProject.id == project_id.value))
            return result.scalars().first()
        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as s:
                orm = await _find(s)
        return _to_entity(orm) if orm else None

    async def find_by_code(self, code: str) -> Project | None:
        async def _find(s):
            result = await s.execute(sa.select(OrmProject).where(OrmProject.code == code))
            return result.scalars().first()
        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as s:
                orm = await _find(s)
        return _to_entity(orm) if orm else None

    async def list_all(self) -> list[Project]:
        async def _all(s):
            result = await s.execute(sa.select(OrmProject))
            return result.scalars().all()
        session = current_session()
        if session is not None:
            orms = await _all(session)
        else:
            async with get_sessionmaker()() as s:
                orms = await _all(s)
        return [_to_entity(o) for o in orms]
