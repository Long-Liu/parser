import pytest

from contexts.shared.application.transaction import (
    NoopTransactionManager,
    configure_transaction_manager,
    get_transaction_manager,
    transactional,
)
from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.infrastructure.domain_event_bus import DomainEventBus


class Saved(DomainEvent):
    pass


@pytest.mark.asyncio
async def test_events_are_dispatched_after_transaction_body():
    original = get_transaction_manager()
    configure_transaction_manager(NoopTransactionManager())
    bus = DomainEventBus()
    order = []

    async def handler(event):
        order.append("event")

    bus.subscribe(Saved, handler)

    @transactional
    async def execute():
        order.append("write")
        await bus.publish([Saved(aggregate_id=1)])
        order.append("return")

    try:
        await execute()
        assert order == ["write", "return", "event"]
    finally:
        configure_transaction_manager(original)
