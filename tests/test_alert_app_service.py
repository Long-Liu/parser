from decimal import Decimal

import pytest

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.alert.domain.alert import AlertLevel, AlertRule, AlertStatus

# noinspection PyProtectedMember
from contexts.alert.infrastructure.repositories import _metric_decimal


def _undecorate(handler):
    """Strip Sanic/openapi decorators to reach the raw handler."""
    while hasattr(handler, "__wrapped__"):
        handler = handler.__wrapped__
    return handler


class FakeMetrics:
    def __init__(self, value=Decimal("8")):
        self.value = value

    async def snapshot(self, _project_id, ym=None):
        return ym or "2026-07", {"gross_profit_rate": self.value}


def test_metric_decimal_rounds_to_database_scale():
    assert _metric_decimal(Decimal("28.54225")) == Decimal("28.5423")


class FakeDispatcher:
    async def dispatch_pending(self):
        pass


class FakeRepository:
    def __init__(self):
        self.alerts = {}
        self.events = []
        self.outbox = []
        self.counts = {}

    @staticmethod
    async def rules():
        return [
            AlertRule(
                "GROSS_PROFIT_LOW",
                "项目毛利率过低",
                "gross_profit_rate",
                "lt",
                Decimal("10"),
                AlertLevel.CRITICAL,
            )
        ]

    async def register_match(self, project_id, rule_code, scope, matched):
        key = (project_id, rule_code, scope)
        self.counts[key] = self.counts.get(key, 0) + 1 if matched else 0
        return self.counts[key]

    async def find_open(self, fingerprint):
        return self.alerts.get(fingerprint)

    async def save(self, alert):
        self.alerts[alert.fingerprint] = alert

    # noinspection PyUnusedParameter
    async def record_event(self, alert, event_type, actor_id=None, note=""):
        self.events.append(event_type)

    async def add_outbox(self, _alert, event_type):
        self.outbox.append(event_type)

    async def get(self, alert_id):
        return next((a for a in self.alerts.values() if a.id == alert_id), None)

    async def detail(self, alert_id):
        alert = await self.get(alert_id)
        if alert is None:
            return None
        return {"id": alert.id, "status": alert.status.value}


@pytest.mark.asyncio
async def test_evaluate_triggers_and_auto_resolves_alert():
    repo = FakeRepository()
    metrics = FakeMetrics()
    # noinspection PyTypeChecker
    service = AlertApplicationService(repo, metrics, FakeDispatcher())

    result = await _undecorate(AlertApplicationService.evaluate)(service, 10, "2026-07")
    assert result["triggered"] == 1
    assert repo.events == ["triggered"]
    assert repo.outbox == ["triggered"]

    metrics.value = Decimal("12")
    result = await _undecorate(AlertApplicationService.evaluate)(service, 10, "2026-07")
    assert result["resolved"] == 1
    assert repo.events[-1] == "auto_resolved"
    assert repo.outbox[-1] == "resolved"


@pytest.mark.asyncio
async def test_ignored_alert_is_retriggered_on_next_crossing():
    """Regression: an IGNORED alert whose metric keeps crossing the threshold
    must be reopened (ACTIVE + 'reopened' event + outbox) on the next
    evaluation, instead of being silently dropped forever."""
    repo = FakeRepository()
    metrics = FakeMetrics()
    # noinspection PyTypeChecker
    service = AlertApplicationService(repo, metrics, FakeDispatcher())

    result = await _undecorate(AlertApplicationService.evaluate)(service, 10, "2026-07")
    assert result["triggered"] == 1
    alert = next(iter(repo.alerts.values()))
    alert.id = 1  # FakeRepository does not assign ids; required by ignore()
    assert alert.status == AlertStatus.ACTIVE

    await service.ignore(alert.id, 99, "暂不关注")
    assert alert.status == AlertStatus.IGNORED
    assert repo.events[-1] == "ignored"

    # Metric still crosses the threshold on the next evaluation → reopened.
    result = await _undecorate(AlertApplicationService.evaluate)(service, 10, "2026-07")
    assert result["triggered"] == 1
    assert repo.events[-1] == "reopened"
    assert repo.outbox[-1] == "reopened"
    assert alert.status == AlertStatus.ACTIVE
