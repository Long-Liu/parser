from __future__ import annotations

from collections.abc import Callable

from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.domain.unit_of_work import UnitOfWork
from contexts.data.domain.data_query import FilterCriterion, Pagination
from contexts.data.domain.repositories import DataQueryRepository


class DataApplicationService:
    def __init__(
        self, repo: DataQueryRepository, uow_factory: Callable[[], UnitOfWork]
    ) -> None:
        self._repo = repo
        self._uow_factory = uow_factory

    async def query(
        self, template_id: str, batch_id: int | None = None,
        page: int = 1, size: int = 200, filters: list[FilterCriterion] | None = None,
    ) -> dict:
        pagination = Pagination(page=page, size=size)
        rows, total = await self._repo.query(
            template_id, batch_id, filters or [], pagination,
        )
        return {
            "data": [r.fields for r in rows],
            "pagination": {"page": page, "size": size, "total": total},
        }

    async def get_by_id(self, template_id: str, row_id: int) -> dict:
        row = await self._repo.get_by_id(template_id, row_id)
        if row is None:
            raise NotFoundError(f"row {row_id} not found in {template_id}")
        return row.fields

    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        async with self._uow_factory() as uow:
            row = await self._repo.get_by_id(template_id, row_id)
            if row is None:
                raise NotFoundError(f"row {row_id} not found in {template_id}")
            await self._repo.delete_by_id(template_id, row_id)
            await uow.commit()
