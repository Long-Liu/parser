"""Domain-event handlers for the alert context.

Alert evaluation used to be invoked synchronously by the parsing and project
application services (a cross-context direct dependency). It is now driven by
domain events published after the originating write transaction commits, so
each evaluation runs in its own transaction via AlertApplicationService's
@transactional boundary.
"""

from __future__ import annotations

import logging

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.parsing.domain.events import ParseJobCompleted, ParseJobConfirmed
from contexts.project.domain.events import (
    ProjectCreated,
    ProjectDeleted,
    ProjectUpdated,
)
from contexts.shared.domain.exceptions import NotFoundError

logger = logging.getLogger("parser.alert.events")


class AlertEventHandlers:
    """Subscribes alert evaluation/cleanup to parsing and project domain events."""

    def __init__(self, alert_service: AlertApplicationService) -> None:
        self._alerts = alert_service

    async def on_parse_job_completed(self, event: ParseJobCompleted) -> None:
        # Preview runs persist no data rows; evaluating them would only advance
        # consecutive-trigger counters, so they are skipped.
        if event.is_preview or event.project_id is None:
            return
        await self._evaluate(event.project_id, event.year_month or None)

    async def on_parse_job_confirmed(self, event: ParseJobConfirmed) -> None:
        if event.project_id is None:
            return
        await self._evaluate(event.project_id, event.year_month or None)

    async def on_project_created(self, event: ProjectCreated) -> None:
        await self._evaluate(_aggregate_int(event.aggregate_id), None)

    async def on_project_updated(self, event: ProjectUpdated) -> None:
        await self._evaluate(_aggregate_int(event.aggregate_id), None)

    async def on_project_deleted(self, event: ProjectDeleted) -> None:
        await self._alerts.delete_project(_aggregate_int(event.aggregate_id))

    async def _evaluate(self, project_id: int, ym: str | None) -> None:
        try:
            await self._alerts.evaluate(project_id, ym)
        except NotFoundError:
            # The project vanished between event publication and evaluation.
            logger.debug("alert evaluation skipped: project %s not found", project_id)


def _aggregate_int(aggregate_id: object) -> int:
    if aggregate_id is None:
        raise ValueError("project event without aggregate_id")
    return int(aggregate_id)
