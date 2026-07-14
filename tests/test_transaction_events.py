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

    async def handler(event):
        order.append("event")

    bus.subscribe(Saved, handler)

    class Service(TransactionalService):
        @transactional
        async def execute(self):
            order.append("write")
            await bus.publish([Saved(aggregate_id=1)])
            order.append("return")

    await Service(NoopTransactionManager()).execute()
    assert order == ["write", "return", "event"]
