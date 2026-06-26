from db.connection import execute
from db.tables import projects


async def create_project(code: str, name: str, created_by: int = None) -> int:
    result = await execute(projects.insert().values(code=code, name=name, created_by=created_by))
    return result.lastrowid


async def list_projects() -> list[dict]:
    result = await execute(projects.select().order_by(projects.c.id.desc()))
    return [dict(r) for r in await result.fetchall()]
