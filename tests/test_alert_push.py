import json

import pytest

from contexts.alert.infrastructure.push import AlertWebSocketHub


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))


@pytest.mark.asyncio
async def test_alert_push_is_filtered_by_project_membership():
    hub = AlertWebSocketHub()
    allowed, denied, admin = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    await hub.connect(1, allowed, [10])
    await hub.connect(2, denied, [20])
    await hub.connect(3, admin, [-1])

    await hub.publish(10, {"event": "alert.triggered", "data": {"id": 1}})

    assert allowed.messages[0]["event"] == "alert.triggered"
    assert denied.messages == []
    assert admin.messages[0]["data"]["id"] == 1
