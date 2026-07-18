from __future__ import annotations

from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.application.transaction import TransactionManager, TransactionalService, transactional
from contexts.data.domain.data_query import FilterCriterion
from contexts.data.domain.repositories import DataQueryRepository
from contexts.shared.domain.pagination import Pagination


class DataApplicationService(TransactionalService):
    def __init__(self, repo: DataQueryRepository,
                 transaction_manager: TransactionManager | None = None) -> None:
        super().__init__(transaction_manager)
        self._repo = repo

    async def query(
        self, template_id: str, batch_id: int | None = None,
        pagination: Pagination | None = None,
        filters: list[FilterCriterion] | None = None,
    ) -> dict:
        if pagination is None:
            pagination = Pagination(1, 200, max_size=500)
        rows, total = await self._repo.query(
            template_id, batch_id, filters or [], pagination,
        )
        return {
            "data": [r.fields for r in rows],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def get_by_id(self, template_id: str, row_id: int) -> dict:
        row = await self._repo.get_by_id(template_id, row_id)
        if row is None:
            raise NotFoundError(f"row {row_id} not found in {template_id}")
        return row.fields

    @transactional
    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        row = await self._repo.get_by_id(template_id, row_id)
        if row is None:
            raise NotFoundError(f"row {row_id} not found in {template_id}")
        await self._repo.delete_by_id(template_id, row_id)
