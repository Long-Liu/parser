from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.shared.domain.pagination import Pagination


class AnalyticsRepository(ABC):
    """Port for the analytics projection and reporting model.

    The projection deliberately has a broad query surface. Declaring the full
    contract here keeps application/interface code independent of ORM tables.
    """

    # ── project projections ─────────────────────────────────────────

    @abstractmethod
    async def project_summary(self, project_ids: list[int] | None = None) -> dict: ...

    @abstractmethod
    async def monthly_data(self, project_id: int, pagination: Pagination) -> dict: ...

    @abstractmethod
    async def month_comparison(self, project_id: int, months: list[str]) -> dict: ...

    @abstractmethod
    async def compare_projects(self, project_ids: list[int] | None, ym: str | None) -> dict: ...

    @abstractmethod
    async def delete_monthly_data(self, project_id: int, ym: str) -> None: ...

    # ── cost / profit reports ───────────────────────────────────────

    @abstractmethod
    async def cost_categories(self, project_ids: list[int] | None, ym: str | None, pagination: Pagination) -> dict: ...

    @abstractmethod
    async def cost_details(self, project_id: int, ym: str | None, pagination: Pagination) -> dict: ...

    @abstractmethod
    async def project_analysis(self, project_id: int, ym: str | None) -> dict: ...

    @abstractmethod
    async def project_profits(
        self, ym: str | None, pagination: Pagination, project_ids: list[int] | None = None
    ) -> dict: ...

    @abstractmethod
    async def budget_lease_writeoffs(
        self,
        ym: str | None,
        pagination: Pagination,
        project_ids: list[int] | None = None,
    ) -> dict: ...

    # ── dashboard ───────────────────────────────────────────────────

    @abstractmethod
    async def dashboard(self, project_ids: list[int] | None = None) -> dict: ...

    @abstractmethod
    async def dashboard_summary(self, project_ids: list[int] | None = None) -> dict: ...

    @abstractmethod
    async def dashboard_status(
        self,
        project_ids: list[int] | None = None,
        pagination: Pagination | None = None,
    ) -> dict: ...

    @abstractmethod
    async def health_radar(self, project_ids: list[int] | None = None) -> dict: ...

    @abstractmethod
    async def dashboard_trends(self, project_ids: list[int] | None = None) -> list[dict]: ...

    @abstractmethod
    async def cost_composition(self, project_ids: list[int] | None = None) -> list[dict]: ...

    # ── misc ────────────────────────────────────────────────────────

    @abstractmethod
    async def ai_analysis(self, project_id: int, ym: str | None) -> dict: ...

    @abstractmethod
    async def compare_ai_analysis(self, project_ids: list[int] | None, ym: str | None) -> dict: ...

    @abstractmethod
    async def global_search(
        self, keyword: str, pagination: Pagination, project_ids: list[int] | None = None, include_users: bool = True
    ) -> dict: ...

    @abstractmethod
    async def sync_status(self) -> dict: ...
