"""Domain-event handlers for the alert context.

Alert evaluation used to be invoked synchronously by the parsing and project
application services (a cross-context direct dependency). It is now driven by
domain events published after the originating write transaction commits, so
each evaluation runs in its own transaction via AlertApplicationService's
@transactional boundary.

Evaluations are serialized per (project_id, ym): the event bus dispatches
handlers as background tasks, so without serialization two rapid uploads for
the same project would evaluate concurrently and race on the alert state rows
(consecutive-trigger counters, open-alert creation) — lost updates and
duplicate alerts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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
        self._locks: dict[tuple[int, str | None], asyncio.Lock] = {}

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
        """Evaluate serially per (project_id, ym).

        The handler task stays in-flight while waiting on the lock, so the
        event bus's drain() covers queued evaluations deterministically.
        """
        key = (project_id, ym)
        # 锁表只增不删：pop 与等待者 acquire 之间存在竞态（释放后检查前等待者
        # 尚未恢复，pop 后新锁会让两任务并发评估同一 key）。键空间 = 项目数 ×
        # 月份数，对本域有界且内存可忽略。
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            try:
                await self._alerts.evaluate(project_id, ym)
            except NotFoundError:
                # The project vanished between event publication and evaluation.
                logger.debug("alert evaluation skipped: project %s not found", project_id)


def _aggregate_int(aggregate_id: Any) -> int:
    if aggregate_id is None:
        raise ValueError("project event without aggregate_id")
    return int(str(aggregate_id))
