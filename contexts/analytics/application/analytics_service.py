from __future__ import annotations

from contexts.analytics.domain.repositories import AnalyticsRepository
from contexts.shared.domain.pagination import Pagination


class AnalyticsApplicationService:
    """Thin application facade over the analytics CQRS read/write model.

    Analytics intentionally spans bounded contexts for reporting, but ORM and
    cross-table details remain in its infrastructure adapter. Every method is
    an explicit one-line delegation to the ``AnalyticsRepository`` port so the
    contract is visible without ``__getattr__`` passthrough.
    """

    def __init__(self, repository: AnalyticsRepository) -> None:
        self._repository = repository

    # ── project projections ─────────────────────────────────────────

    async def project_summary(self, project_ids: list[int] | None = None) -> dict:
        return await self._repository.project_summary(project_ids)

    async def monthly_data(self, project_id: int, pagination: Pagination) -> dict:
        return await self._repository.monthly_data(project_id, pagination)

    async def month_comparison(self, project_id: int, months: list[str]) -> dict:
        return await self._repository.month_comparison(project_id, months)

    async def compare_projects(self, project_ids: list[int] | None, ym: str | None) -> dict:
        return await self._repository.compare_projects(project_ids, ym)

    async def delete_monthly_data(self, project_id: int, ym: str) -> None:
        return await self._repository.delete_monthly_data(project_id, ym)

    # ── cost / profit reports ───────────────────────────────────────

    async def cost_categories(self, project_ids: list[int] | None, ym: str | None, pagination: Pagination) -> dict:
        return await self._repository.cost_categories(project_ids, ym, pagination)

    async def cost_details(self, project_id: int, ym: str | None, pagination: Pagination) -> dict:
        return await self._repository.cost_details(project_id, ym, pagination)

    async def project_analysis(self, project_id: int, ym: str | None) -> dict:
        return await self._repository.project_analysis(project_id, ym)

    async def project_profits(
        self, ym: str | None, pagination: Pagination, project_ids: list[int] | None = None
    ) -> dict:
        return await self._repository.project_profits(ym, pagination, project_ids)

    async def budget_lease_writeoffs(
        self,
        ym: str | None,
        pagination: Pagination,
        project_ids: list[int] | None = None,
    ) -> dict:
        return await self._repository.budget_lease_writeoffs(
            ym,
            pagination,
            project_ids,
        )

    # ── dashboard ───────────────────────────────────────────────────

    async def dashboard(self, project_ids: list[int] | None = None) -> dict:
        return await self._repository.dashboard(project_ids)

    async def dashboard_summary(self, project_ids: list[int] | None = None) -> dict:
        return await self._repository.dashboard_summary(project_ids)

    async def dashboard_status(
        self,
        project_ids: list[int] | None = None,
        pagination: Pagination | None = None,
    ) -> dict:
        return await self._repository.dashboard_status(project_ids, pagination)

    async def health_radar(self, project_ids: list[int] | None = None) -> dict:
        return await self._repository.health_radar(project_ids)

    async def dashboard_trends(self, project_ids: list[int] | None = None) -> list[dict]:
        return await self._repository.dashboard_trends(project_ids)

    async def cost_composition(self, project_ids: list[int] | None = None) -> list[dict]:
        return await self._repository.cost_composition(project_ids)

    # ── misc ────────────────────────────────────────────────────────

    async def ai_analysis(self, project_id: int, ym: str | None) -> dict:
        return await self._repository.ai_analysis(project_id, ym)

    async def compare_ai_analysis(self, project_ids: list[int] | None, ym: str | None) -> dict:
        return await self._repository.compare_ai_analysis(project_ids, ym)

    async def global_search(
        self, keyword: str, pagination: Pagination, project_ids: list[int] | None = None, include_users: bool = True
    ) -> dict:
        return await self._repository.global_search(keyword, pagination, project_ids, include_users)

    async def sync_status(self) -> dict:
        return await self._repository.sync_status()
