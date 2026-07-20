from __future__ import annotations

from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.domain.base_entity import Entity, IdType


class AggregateRoot(Entity[IdType]):
    """Aggregate root base — collects domain events for publishing after persistence."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = self._events
        self._events = []
        return events
