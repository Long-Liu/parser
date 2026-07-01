
import sqlalchemy as sa

from db.models import UploadBatch, UploadLog
from repositories.base_repository import BaseRepo


class BatchRepo(BaseRepo):
    model = UploadBatch

    @classmethod
    async def list_filtered(cls, project_id: int | None = None,
                            ym: str | None = None) -> list[dict]:
        conditions = []
        if project_id is not None:
            conditions.append(cls._t().c.project_id == project_id)
        if ym:
            conditions.append(cls._t().c.ym == ym)
        if conditions:
            return await cls.list(
                sa.and_(*conditions),
                order_by=cls._t().c.id.desc(),
            )
        return await cls.list(order_by=cls._t().c.id.desc())

    @classmethod
    async def get_by_id(cls, batch_id: int) -> dict | None:
        return await cls.get(cls._t().c.id == batch_id)

    @classmethod
    async def update_status(cls, batch_id: int, status: str) -> None:
        await cls.update(cls._t().c.id == batch_id, status=status)

    @classmethod
    async def delete_by_id(cls, batch_id: int) -> None:
        await cls.delete(cls._t().c.id == batch_id)


class LogRepo(BaseRepo):
    model = UploadLog

    @classmethod
    async def list_by_batch(cls, batch_id: int) -> list[dict]:
        return await cls.list(
            cls._t().c.batch_id == batch_id,
            order_by=cls._t().c.id,
        )
