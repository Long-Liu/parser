from decimal import Decimal

import pytest

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.alert.domain.alert import AlertLevel, AlertRule


class FakeMetrics:
    def __init__(self, value=Decimal("8")):
        self.value = value

    async def snapshot(self, project_id, ym=None):
        return ym or "2026-07", {"gross_profit_rate": self.value}


class FakeDispatcher:
    async def dispatch_pending(self):
        pass


class FakeRepository:
    def __init__(self):
        self.alerts = {}
        self.events = []
        self.outbox = []
        self.counts = {}

    async def rules(self):
        return [AlertRule(
            "GROSS_PROFIT_LOW", "项目毛利率过低", "gross_profit_rate",
            "lt", Decimal("10"), AlertLevel.CRITICAL,
        )]

    async def register_match(self, project_id, rule_code, scope, matched):
        key = (project_id, rule_code, scope)
        self.counts[key] = self.counts.get(key, 0) + 1 if matched else 0
        return self.counts[key]

    async def find_open(self, fingerprint):
        return self.alerts.get(fingerprint)

    async def save(self, alert):
        if alert.id is None:
            alert.id = len(self.alerts) + 1
        self.alerts[alert.fingerprint] = alert

    async def record_event(self, alert, event_type, actor_id=None, note=""):
        self.events.append(event_type)

    async def add_outbox(self, alert, event_type):
        self.outbox.append(event_type)

    async def get(self, alert_id):
        return next((a for a in self.alerts.values() if a.id == alert_id), None)


@pytest.mark.asyncio
async def test_evaluate_triggers_and_auto_resolves_alert():
    repo = FakeRepository()
    metrics = FakeMetrics()
    service = AlertApplicationService(repo, metrics, FakeDispatcher())

    result = await AlertApplicationService.evaluate.__wrapped__(service, 10, "2026-07")
    assert result["triggered"] == 1
    assert repo.events == ["triggered"]
    assert repo.outbox == ["triggered"]

    metrics.value = Decimal("12")
    result = await AlertApplicationService.evaluate.__wrapped__(service, 10, "2026-07")
    assert result["resolved"] == 1
    assert repo.events[-1] == "auto_resolved"
    assert repo.outbox[-1] == "resolved"
