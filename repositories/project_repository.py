from db.models import Project
from repositories.base_repository import BaseRepo


class ProjectRepo(BaseRepo):
    model = Project

    @classmethod
    async def list_page(cls, *, limit: int, offset: int) -> list[dict]:
        return await cls.list(
            order_by=cls._t().c.id.desc(),
            limit=limit,
            offset=offset,
        )

    @classmethod
    async def get_by_id(cls, project_id: int) -> dict | None:
        return await cls.get(cls._t().c.id == project_id)

    @classmethod
    async def get_by_code(cls, code: str) -> dict | None:
        return await cls.get(cls._t().c.code == code)

    @classmethod
    async def update_by_id(cls, project_id: int, **values) -> None:
        await cls.update(cls._t().c.id == project_id, **values)

    @classmethod
    async def delete_by_id(cls, project_id: int) -> None:
        await cls.delete(cls._t().c.id == project_id)
