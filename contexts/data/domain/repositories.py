from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.data.domain.data_query import DataRow, Pagination, FilterCriterion


class DataQueryRepository(Repository):
    @abstractmethod
    async def query(
        self, template_id: str, batch_id: int | None,
        filters: list[FilterCriterion], pagination: Pagination,
    ) -> tuple[list[DataRow], int]: ...

    @abstractmethod
    async def get_by_id(self, template_id: str, row_id: int) -> DataRow | None: ...

    @abstractmethod
    async def delete_by_id(self, template_id: str, row_id: int) -> None: ...
