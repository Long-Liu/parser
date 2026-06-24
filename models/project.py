from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from parser.db.models import Project


async def create_project(session: AsyncSession, code: str, name: str, created_by: int = None) -> int:
    project = Project(code=code, name=name, created_by=created_by)
    session.add(project)
    await session.flush()
    return project.id


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.id.desc()))
    return result.scalars().all()
