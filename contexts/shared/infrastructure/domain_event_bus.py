from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.application.transaction import defer_after_commit

logger = logging.getLogger("parser.event_bus")
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class DomainEventBus(EventPublisher):
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, events: list[DomainEvent]) -> None:
        snapshot = list(events)
        if defer_after_commit(lambda: self._publish_now(snapshot)):
            return
        await self._publish_now(snapshot)

    async def _publish_now(self, events: list[DomainEvent]) -> None:
        for event in events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception("Event handler failed for %s", type(event).__name__)


# ponytail: module-level singleton — good enough until multiple buses are needed
domain_event_bus = DomainEventBus()


@dataclass(frozen=True)
class _DemoEvent(DomainEvent):
    data: str = ""


def _demo():
    received: list[str] = []

    async def handler(event: _DemoEvent) -> None:
        received.append(event.data)

    bus = DomainEventBus()
    bus.subscribe(_DemoEvent, handler)
    import asyncio
    asyncio.run(bus.publish([_DemoEvent(aggregate_id=1, data="hello")]))
    assert received == ["hello"]
    print("domain_event_bus: OK")


if __name__ == "__main__":
    _demo()
