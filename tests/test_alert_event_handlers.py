"""Wiring tests: alert evaluation is driven by subscribed domain events."""

import pytest

from contexts.alert.application.event_handlers import AlertEventHandlers
from contexts.parsing.domain.events import ParseJobCompleted, ParseJobConfirmed
from contexts.project.domain.events import (
    ProjectCreated,
    ProjectDeleted,
    ProjectUpdated,
)
from contexts.shared.infrastructure.domain_event_bus import DomainEventBus


class FakeAlertService:
    def __init__(self) -> None:
        self.evaluations: list[tuple[int, str | None]] = []
        self.deleted_projects: list[int] = []

    async def evaluate(self, project_id: int, ym: str | None = None) -> dict:
        self.evaluations.append((project_id, ym))
        return {}

    async def delete_project(self, project_id: int) -> None:
        self.deleted_projects.append(project_id)


def _wired_bus(alerts: FakeAlertService) -> DomainEventBus:
    handlers = AlertEventHandlers(alerts)
    bus = DomainEventBus()
    bus.subscribe(ParseJobCompleted, handlers.on_parse_job_completed)
    bus.subscribe(ParseJobConfirmed, handlers.on_parse_job_confirmed)
    bus.subscribe(ProjectCreated, handlers.on_project_created)
    bus.subscribe(ProjectUpdated, handlers.on_project_updated)
    bus.subscribe(ProjectDeleted, handlers.on_project_deleted)
    return bus


@pytest.mark.asyncio
async def test_parse_job_completed_triggers_alert_evaluation():
    alerts = FakeAlertService()
    bus = _wired_bus(alerts)
    await bus.publish([ParseJobCompleted(
        aggregate_id=1, project_id=7, year_month="2026-07",
    )])
    assert alerts.evaluations == [(7, "2026-07")]


@pytest.mark.asyncio
async def test_preview_completion_does_not_trigger_alert_evaluation():
    alerts = FakeAlertService()
    bus = _wired_bus(alerts)
    await bus.publish([ParseJobCompleted(
        aggregate_id=1, project_id=7, year_month="2026-07", is_preview=True,
    )])
    assert alerts.evaluations == []


@pytest.mark.asyncio
async def test_parse_job_confirmed_triggers_alert_evaluation():
    alerts = FakeAlertService()
    bus = _wired_bus(alerts)
    await bus.publish([ParseJobConfirmed(
        aggregate_id=1, project_id=7, year_month="2026-07",
    )])
    assert alerts.evaluations == [(7, "2026-07")]


@pytest.mark.asyncio
async def test_project_created_and_updated_trigger_alert_evaluation():
    alerts = FakeAlertService()
    bus = _wired_bus(alerts)
    await bus.publish([ProjectCreated(aggregate_id=5, code="P005", name="新项目")])
    await bus.publish([ProjectUpdated(aggregate_id=5, changed_fields=("progress",))])
    assert alerts.evaluations == [(5, None), (5, None)]


@pytest.mark.asyncio
async def test_project_deleted_triggers_alert_cleanup():
    alerts = FakeAlertService()
    bus = _wired_bus(alerts)
    await bus.publish([ProjectDeleted(aggregate_id=5, code="P005")])
    assert alerts.deleted_projects == [5]
    assert alerts.evaluations == []


def test_container_registers_alert_event_subscriptions():
    from contexts.container import build_container
    from contexts.shared.infrastructure.config import Settings

    components = build_container(Settings())
    bus = components.event_bus
    for event_type in (
        ParseJobCompleted, ParseJobConfirmed,
        ProjectCreated, ProjectUpdated, ProjectDeleted,
    ):
        assert bus.subscribers(event_type), (
            f"no subscriber registered for {event_type.__name__}"
        )
