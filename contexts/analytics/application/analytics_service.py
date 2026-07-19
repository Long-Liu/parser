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

    async def compare_projects(self, project_ids: list[int], ym: str | None) -> dict:
        return await self._repository.compare_projects(project_ids, ym)

    async def delete_monthly_data(self, project_id: int, ym: str) -> None:
        return await self._repository.delete_monthly_data(project_id, ym)

    # ── cost / profit reports ───────────────────────────────────────

    async def cost_categories(self, project_ids: list[int], ym: str | None,
                              pagination: Pagination) -> dict:
        return await self._repository.cost_categories(project_ids, ym, pagination)

    async def cost_details(self, project_id: int, ym: str | None,
                           pagination: Pagination) -> dict:
        return await self._repository.cost_details(project_id, ym, pagination)

    async def project_analysis(self, project_id: int, ym: str | None) -> dict:
        return await self._repository.project_analysis(project_id, ym)

    async def project_profits(self, ym: str | None, pagination: Pagination,
                              project_ids: list[int] | None = None) -> dict:
        return await self._repository.project_profits(ym, pagination, project_ids)

    # ── milestones / progress ───────────────────────────────────────

    async def milestones(self, project_id: int, pagination: Pagination) -> dict:
        return await self._repository.milestones(project_id, pagination)

    async def project_progress(self, project_id: int, pagination: Pagination) -> dict:
        return await self._repository.project_progress(project_id, pagination)

    async def create_milestone(self, project_id: int, data: dict) -> dict:
        return await self._repository.create_milestone(project_id, data)

    async def update_milestone(self, project_id: int, milestone_id: int,
                               data: dict) -> dict:
        return await self._repository.update_milestone(project_id, milestone_id, data)

    async def delete_milestone(self, project_id: int, milestone_id: int) -> None:
        return await self._repository.delete_milestone(project_id, milestone_id)

    # ── dashboard ───────────────────────────────────────────────────

    async def dashboard(self, project_ids: list[int] | None = None) -> dict:
        return await self._repository.dashboard(project_ids)

    async def health_radar(self, project_ids: list[int] | None = None) -> dict:
        return await self._repository.health_radar(project_ids)

    async def dashboard_trends(self, project_ids: list[int] | None = None) -> list[dict]:
        return await self._repository.dashboard_trends(project_ids)

    async def cost_composition(self, project_ids: list[int] | None = None) -> list[dict]:
        return await self._repository.cost_composition(project_ids)

    # ── notifications ───────────────────────────────────────────────

    async def notifications(self, user_id: int, pagination: Pagination,
                            unread_only: bool = False,
                            project_ids: list[int] | None = None) -> dict:
        return await self._repository.notifications(
            user_id, pagination, unread_only, project_ids)

    async def create_notification(self, data: dict) -> dict:
        return await self._repository.create_notification(data)

    async def mark_notification_read(self, user_id: int, notification_id: int) -> None:
        return await self._repository.mark_notification_read(user_id, notification_id)

    async def mark_all_notifications_read(self, user_id: int) -> int:
        return await self._repository.mark_all_notifications_read(user_id)

    async def delete_notification(self, user_id: int, notification_id: int) -> None:
        return await self._repository.delete_notification(user_id, notification_id)

    async def clear_notifications(self, user_id: int) -> int:
        return await self._repository.clear_notifications(user_id)

    # ── misc ────────────────────────────────────────────────────────

    async def ai_analysis(self, project_id: int, ym: str | None) -> dict:
        return await self._repository.ai_analysis(project_id, ym)

    async def compare_ai_analysis(self, project_ids: list[int], ym: str | None) -> dict:
        return await self._repository.compare_ai_analysis(project_ids, ym)

    async def global_search(self, keyword: str, pagination: Pagination,
                            project_ids: list[int] | None = None,
                            include_users: bool = True) -> dict:
        return await self._repository.global_search(
            keyword, pagination, project_ids, include_users)

    async def sync_status(self) -> dict:
        return await self._repository.sync_status()
