from __future__ import annotations

import sqlalchemy as sa

from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.data.domain.data_query import DataRow, Pagination, FilterCriterion
from contexts.data.domain.repositories import DataQueryRepository


class DataQueryRepositoryImpl(DataQueryRepository):
    async def query(
            self, template_id: str, batch_id: int | None,
            filters: list[FilterCriterion], pagination: Pagination,
    ) -> tuple[list[DataRow], int]:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return [], 0
        t = model.__table__
        stmt = sa.select(t)
        if batch_id is not None:
            stmt = stmt.where(t.c.batch_id == batch_id)
        for f in filters:
            col = getattr(t.c, f.field, None)
            if col is not None and f.operator == "eq":
                stmt = stmt.where(col == f.value)
            elif col is not None and f.operator == "like":
                stmt = stmt.where(col.like(f"%{f.value}%"))

        count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
        stmt = stmt.limit(pagination.size).offset(pagination.offset)

        async def _query(session):
            total = (await session.execute(count_stmt)).scalar() or 0
            result = await session.execute(stmt)
            return [DataRow(fields=dict(r._mapping)) for r in result.all()], total

        session = current_session()
        if session is not None:
            return await _query(session)
        async with get_sessionmaker()() as s:
            return await _query(s)

    async def get_by_id(self, template_id: str, row_id: int) -> DataRow | None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return None
        t = model.__table__

        async def _get(s):
            r = (await s.execute(sa.select(t).where(t.c.id == row_id))).first()
            return DataRow(fields=dict(r._mapping)) if r else None

        session = current_session()
        if session is not None:
            return await _get(session)
        async with get_sessionmaker()() as s:
            return await _get(s)

    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return
        t = model.__table__

        async def _delete(s):
            await s.execute(sa.delete(t).where(t.c.id == row_id))

        session = current_session()
        if session is None:
            raise RuntimeError("DataQueryRepository.delete_by_id requires an active UnitOfWork")
        await _delete(session)
