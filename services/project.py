"""Project service."""

from repositories.project import ProjectRepo


async def list_projects() -> list[dict]:
    return await ProjectRepo.list(order_by=ProjectRepo.table.c.id.desc())


async def create_project(code: str, name: str, user_id: int) -> dict:
    pid = await ProjectRepo.insert(code=code, name=name, created_by=user_id)
    return {"id": pid, "code": code}
