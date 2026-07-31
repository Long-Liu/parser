from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TypeVar

from contexts.shared.application.transaction import defer_after_commit
from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.domain.event_publisher import EventPublisher

logger = logging.getLogger("parser.event_bus")
EventHandler = Callable[[DomainEvent], Awaitable[None]]
EventT = TypeVar("EventT", bound=DomainEvent)


class DomainEventBus(EventPublisher):
    """Dispatches domain events to their subscribed handlers.

    Handlers run as background tasks: evaluation work (alert checks, …) must
    not extend the request coroutine that committed the originating write.
    ``drain`` exists for tests and shutdown that need deterministic completion.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._tasks: set[asyncio.Task] = set()

    def subscribe(
        self,
        event_type: type[EventT],
        handler: Callable[[EventT], Awaitable[None]],
    ) -> None:
        self._handlers[event_type].append(handler)

    def subscribers(self, event_type: type[DomainEvent]) -> tuple[EventHandler, ...]:
        """Read-only view of the handlers registered for an event type."""
        return tuple(self._handlers.get(event_type, ()))

    async def publish(self, events: list[DomainEvent]) -> None:
        snapshot = list(events)
        if defer_after_commit(lambda: self._publish_now(snapshot)):
            return
        await self._publish_now(snapshot)

    async def _publish_now(self, events: list[DomainEvent]) -> None:
        for event in events:
            for handler in self._handlers.get(type(event), []):
                self._spawn(handler, event)

    def _spawn(self, handler: EventHandler, event: DomainEvent) -> None:
        task = asyncio.create_task(self._run_handler(handler, event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _run_handler(handler: EventHandler, event: DomainEvent) -> None:
        # noinspection PyBroadException
        try:
            await handler(event)
        except Exception:
            logger.exception("Event handler failed for %s", type(event).__name__)

    async def drain(self) -> None:
        """Await completion of every in-flight handler task."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
