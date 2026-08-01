"""Regression tests for alert outbox delivery semantics.

A pending outbox message must NOT be marked "sent" while no subscriber can
receive it — it is retried with backoff instead (the old code always marked
rows sent because AlertWebSocketHub.publish never raised)."""

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.alert.infrastructure.push import AlertWebSocketHub, TortoiseAlertOutboxDispatcher
from contexts.alert.infrastructure.tables import AlertOutboxModel

# noinspection PyProtectedMember
from contexts.shared.infrastructure.database.engine import _MODEL_MODULES


@pytest.fixture
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": list(_MODEL_MODULES)},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


async def test_undelivered_message_is_retried_not_marked_sent(db):
    row = await AlertOutboxModel.create(
        event_type="alert.triggered",
        aggregate_id=1,
        project_id=10,
        payload={"id": 1},
        status="pending",
    )
    dispatcher = TortoiseAlertOutboxDispatcher(AlertWebSocketHub())

    await dispatcher.dispatch_pending()

    await row.refresh_from_db()
    assert row.status == "pending"  # not silently "sent"
    assert row.retry_count == 1
    assert row.next_retry_at is not None
    assert row.last_error == "no connected subscriber"


async def test_message_is_sent_once_subscriber_connects(db):
    row = await AlertOutboxModel.create(
        event_type="alert.triggered",
        aggregate_id=2,
        project_id=10,
        payload={"id": 2},
        status="pending",
    )
    hub = AlertWebSocketHub()
    ws = FakeWebSocket()
    await hub.connect(1, ws, [10])
    dispatcher = TortoiseAlertOutboxDispatcher(hub)

    await dispatcher.dispatch_pending()

    await row.refresh_from_db()
    assert row.status == "sent"
    assert row.sent_at is not None
    assert len(ws.messages) == 1


async def test_message_dropped_after_max_retries(db):
    from contexts.alert.application.constants import OUTBOX_MAX_RETRIES

    row = await AlertOutboxModel.create(
        event_type="alert.triggered",
        aggregate_id=3,
        project_id=10,
        payload={"id": 3},
        status="pending",
        retry_count=OUTBOX_MAX_RETRIES,
        next_retry_at=None,
    )
    dispatcher = TortoiseAlertOutboxDispatcher(AlertWebSocketHub())

    await dispatcher.dispatch_pending()

    await row.refresh_from_db()
    assert row.status == "sent"  # terminal drop with a trace, outbox stops growing
    assert row.last_error == "no connected subscriber after retries"
