from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from contexts.shared.domain.exceptions import ValidationError


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


@dataclass(frozen=True)
class AlertRule:
    code: str
    name: str
    metric: str
    operator: str
    threshold: Decimal
    level: AlertLevel
    enabled: bool = True
    consecutive_triggers: int = 1
    auto_resolve: bool = True

    def matches(self, value: Decimal) -> bool:
        operations = {
            "gt": value > self.threshold,
            "gte": value >= self.threshold,
            "lt": value < self.threshold,
            "lte": value <= self.threshold,
            "eq": value == self.threshold,
        }
        if self.operator not in operations:
            raise ValidationError(f"unsupported alert operator: {self.operator}")
        return operations[self.operator]


class Alert:
    def __init__(self, *, alert_id: int | None, project_id: int, rule_code: str,
                 alert_type: str, level: AlertLevel, title: str, message: str,
                 metric_value: Decimal, threshold_value: Decimal,
                 fingerprint: str, ym: str | None = None,
                 status: AlertStatus = AlertStatus.ACTIVE,
                 trigger_count: int = 1,
                 first_triggered_at: datetime | None = None,
                 last_triggered_at: datetime | None = None) -> None:
        self.id = alert_id
        self.project_id = project_id
        self.rule_code = rule_code
        self.alert_type = alert_type
        self.level = level
        self.title = title
        self.message = message
        self.metric_value = metric_value
        self.threshold_value = threshold_value
        self.fingerprint = fingerprint
        self.ym = ym
        self.status = status
        self.trigger_count = trigger_count
        now = datetime.now(timezone.utc)
        self.first_triggered_at = first_triggered_at or now
        self.last_triggered_at = last_triggered_at or now

    @property
    def open(self) -> bool:
        return self.status in {AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED}

    def retrigger(self, value: Decimal, level: AlertLevel, message: str) -> str:
        previous = self.level
        self.metric_value = value
        self.level = level
        self.message = message
        self.last_triggered_at = datetime.now(timezone.utc)
        self.trigger_count += 1
        if self.status in {AlertStatus.RESOLVED, AlertStatus.IGNORED}:
            self.status = AlertStatus.ACTIVE
            return "reopened"
        order = {AlertLevel.INFO: 0, AlertLevel.WARNING: 1, AlertLevel.CRITICAL: 2}
        return "escalated" if order[level] > order[previous] else "triggered"

    def acknowledge(self) -> None:
        if self.status != AlertStatus.ACTIVE:
            raise ValidationError("only active alerts can be acknowledged")
        self.status = AlertStatus.ACKNOWLEDGED

    def resolve(self) -> None:
        if not self.open:
            raise ValidationError("alert is already closed")
        self.status = AlertStatus.RESOLVED

    def ignore(self) -> None:
        if not self.open:
            raise ValidationError("alert is already closed")
        self.status = AlertStatus.IGNORED
