from decimal import Decimal

import pytest

from contexts.alert.domain.alert import Alert, AlertLevel, AlertRule, AlertStatus
from contexts.shared.domain.exceptions import ValidationError


def make_alert():
    return Alert(
        alert_id=1, project_id=10, rule_code="LOW_MARGIN",
        alert_type="gross_profit_rate", level=AlertLevel.WARNING,
        title="毛利率过低", message="低于阈值",
        metric_value=Decimal("8"), threshold_value=Decimal("10"),
        fingerprint="10:LOW_MARGIN:2026-07", ym="2026-07",
    )


def test_alert_lifecycle_and_reopen():
    alert = make_alert()
    alert.acknowledge()
    assert alert.status == AlertStatus.ACKNOWLEDGED
    alert.resolve()
    assert alert.status == AlertStatus.RESOLVED
    assert alert.retrigger(Decimal("6"), AlertLevel.CRITICAL, "再次过低") == "reopened"
    assert alert.status == AlertStatus.ACTIVE
    assert alert.level == AlertLevel.CRITICAL


def test_alert_rejects_invalid_transitions():
    alert = make_alert()
    alert.ignore()
    with pytest.raises(ValidationError):
        alert.resolve()


def test_rule_comparison():
    rule = AlertRule("R", "成本偏差", "cost", "gt", Decimal("10"), AlertLevel.WARNING)
    assert rule.matches(Decimal("10.1"))
    assert not rule.matches(Decimal("10"))
