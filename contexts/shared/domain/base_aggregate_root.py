from __future__ import annotations

from contexts.shared.domain.base_entity import Entity
from contexts.shared.domain.base_domain_event import DomainEvent


class AggregateRoot(Entity):
    """Aggregate root base — collects domain events for publishing after persistence."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = self._events
        self._events = []
        return events


class _DemoRegistered(DomainEvent):
    pass


def _demo():
    class _DemoAR(AggregateRoot):
        def __init__(self, ar_id: int) -> None:
            super().__init__()
            self.id = ar_id

        def activate(self) -> None:
            self.record(_DemoRegistered(aggregate_id=self.id))

    ar = _DemoAR(42)
    ar.activate()
    events = ar.pull_events()
    assert len(events) == 1, "should have recorded one event"
    assert events[0].aggregate_id == 42, "event should reference aggregate"
    assert len(ar.pull_events()) == 0, "pull_events should drain"
    print("base_aggregate_root: OK")


if __name__ == "__main__":
    _demo()
