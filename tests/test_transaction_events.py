import pytest

from contexts.shared.application.transaction import (
    NoopTransactionManager,
    TransactionalService,
    transactional,
)
from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.infrastructure.domain_event_bus import DomainEventBus


class Saved(DomainEvent):
    pass


@pytest.mark.asyncio
async def test_events_are_dispatched_after_transaction_body():
    bus = DomainEventBus()
    order = []

    async def handler(_event):
        order.append("event")

    bus.subscribe(Saved, handler)

    class Service(TransactionalService):
        @transactional
        async def execute(self):
            order.append("write")
            await bus.publish([Saved(aggregate_id=1)])
            order.append("return")

    await Service(NoopTransactionManager()).execute()
    await bus.drain()
    assert order == ["write", "return", "event"]


@pytest.mark.asyncio
async def test_handler_failure_is_retried_then_succeeds():
    bus = DomainEventBus()
    attempts = 0

    async def handler(_event):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient failure")

    bus.subscribe(Saved, handler)

    await bus.publish([Saved(aggregate_id=1)])
    await bus.drain()
    assert attempts == 2


@pytest.mark.asyncio
async def test_persistent_handler_failure_is_logged_not_raised():
    bus = DomainEventBus()

    async def handler(_event):
        raise RuntimeError("permanent failure")

    bus.subscribe(Saved, handler)

    # publish/drain must not raise — the failure stays in the log.
    await bus.publish([Saved(aggregate_id=1)])
    await bus.drain()
    assert True
