from __future__ import annotations

from contexts.analytics.domain.repositories import AnalyticsRepository


class AnalyticsApplicationService:
    """Thin application facade over the analytics CQRS read/write model.

    Analytics intentionally spans bounded contexts for reporting, but ORM and
    cross-table details remain in its infrastructure adapter.
    """

    def __init__(self, repository: AnalyticsRepository) -> None:
        self._repository = repository

    def __getattr__(self, name: str):
        return getattr(self._repository, name)
