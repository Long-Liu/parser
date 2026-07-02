from __future__ import annotations

from contexts.shared.domain.base_entity import Entity, IdType
from contexts.shared.domain.base_domain_event import DomainEvent


class AggregateRoot(Entity[IdType]):
    """Aggregate root base — collects domain events for publishing after persistence.

    Subclasses do NOT need to call ``super().__init__()`` — ``_events`` is
    lazily initialised on first ``record()`` or ``pull_events()`` call.
    """

    def record(self, event: DomainEvent) -> None:
        try:
            self._events.append(event)
        except AttributeError:
            self._events: list[DomainEvent] = [event]

    def pull_events(self) -> list[DomainEvent]:
        try:
            events = self._events
            self._events = []
            return events
        except AttributeError:
            return []


class _DemoRegistered(DomainEvent):
    pass


def _demo():
    # Normal path — super().__init__() is harmless (falls through to object)
    class _DemoAR(AggregateRoot[int]):
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

    # Safety net — subclass that forgets super().__init__()
    class _ForgetfulAR(AggregateRoot[int]):
        def __init__(self, ar_id: int) -> None:
            self.id = ar_id  # oops — forgot super().__init__()

        def go(self) -> None:
            self.record(_DemoRegistered(aggregate_id=self.id))

    f = _ForgetfulAR(99)
    f.go()
    assert len(f.pull_events()) == 1, "should work even without super().__init__()"
    assert f.pull_events() == [], "pull_events should drain"
    print("base_aggregate_root: OK")


if __name__ == "__main__":
    _demo()
