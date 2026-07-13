from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from contexts.alert.domain.alert import Alert, AlertLevel, AlertRule, AlertStatus
from contexts.alert.domain.repositories import AlertMetricProvider, AlertRepository
from contexts.alert.infrastructure.tables import (
    AlertEventModel,
    AlertModel,
    AlertOutboxModel,
    AlertRuleModel,
    AlertRuleStateModel,
)
from contexts.analytics.infrastructure.analytics_repository import _or_default
from contexts.shared.infrastructure.database.queryset_helpers import fetch_values_list
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.tables import Project
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.database.tables import (
    DataDynamicIndicator,
    DataGrossProfit,
)

DEFAULT_RULES = (
    ("COST_DEVIATION_HIGH", "成本偏差过高", "cost_deviation_rate", "gt", "10", "warning"),
    ("GROSS_PROFIT_LOW", "项目毛利率过低", "gross_profit_rate", "lt", "10", "critical"),
    ("PROJECT_PROGRESS_DELAYED", "项目进度滞后", "progress_delay", "gt", "10", "warning"),
    ("PROJECT_MANUAL_WARNING", "项目手动预警", "manual_warning", "eq", "1", "warning"),
)


def _entity(row: AlertModel) -> Alert:
    return Alert(
        alert_id=row.id, project_id=row.project_id, rule_code=row.rule_code,
        alert_type=row.alert_type, level=AlertLevel(row.level), title=row.title,
        message=row.message, metric_value=Decimal(row.metric_value),
        threshold_value=Decimal(row.threshold_value), fingerprint=row.fingerprint,
        ym=row.ym, status=AlertStatus(row.status), trigger_count=row.trigger_count,
        first_triggered_at=row.first_triggered_at,
        last_triggered_at=row.last_triggered_at,
    )


def _payload(row: AlertModel) -> dict:
    return {
        "id": row.id, "project_id": row.project_id, "rule_code": row.rule_code,
        "type": row.alert_type, "level": row.level, "title": row.title,
        "message": row.message, "metric_value": float(row.metric_value),
        "threshold_value": float(row.threshold_value), "ym": row.ym,
        "status": row.status, "trigger_count": row.trigger_count,
        "first_triggered_at": row.first_triggered_at.isoformat(),
        "last_triggered_at": row.last_triggered_at.isoformat(),
        "acknowledged_by": row.acknowledged_by,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "resolved_by": row.resolved_by,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolution_note": row.resolution_note,
    }


class TortoiseAlertRepository(AlertRepository):
    async def register_match(self, project_id: int, rule_code: str,
                             scope: str, matched: bool) -> int:
        row, _ = await AlertRuleStateModel.get_or_create(
            project_id=project_id, rule_code=rule_code, scope=scope,
            defaults={"consecutive_count": 0},
        )
        row.consecutive_count = row.consecutive_count + 1 if matched else 0
        await row.save(update_fields=["consecutive_count", "updated_at"])
        return row.consecutive_count

    async def rules(self) -> list[AlertRule]:
        if not await AlertRuleModel.exists():
            for code, name, metric, operator, threshold, level in DEFAULT_RULES:
                await AlertRuleModel.get_or_create(code=code, defaults={
                    "name": name, "metric": metric, "operator": operator,
                    "threshold": Decimal(threshold), "level": level,
                    "enabled": True, "consecutive_triggers": 1,
                    "auto_resolve": True,
                })
        rows = await AlertRuleModel.filter(enabled=True).order_by("id")
        return [AlertRule(
            code=row.code, name=row.name, metric=row.metric,
            operator=row.operator, threshold=Decimal(row.threshold),
            level=AlertLevel(row.level), enabled=row.enabled,
            consecutive_triggers=row.consecutive_triggers,
            auto_resolve=row.auto_resolve,
        ) for row in rows]

    async def rule_records(self, pagination: Pagination) -> tuple[list, int]:
        await self.rules()  # installs defaults on first use
        query = AlertRuleModel.all()
        total = await query.count()
        rows = await query.order_by("id").offset(pagination.offset).limit(pagination.size)
        return [self._rule_payload(row) for row in rows], total

    async def update_rule(self, rule_id: int, values: dict) -> dict | None:
        row = await AlertRuleModel.get_or_none(id=rule_id)
        if row is None:
            return None
        for field, value in values.items():
            setattr(row, field, value)
        await row.save(update_fields=list(values))
        return self._rule_payload(row)

    @staticmethod
    def _rule_payload(row: AlertRuleModel) -> dict:
        return {
            "id": row.id, "code": row.code, "name": row.name,
            "metric": row.metric, "operator": row.operator,
            "threshold": float(row.threshold), "level": row.level,
            "enabled": row.enabled,
            "consecutive_triggers": row.consecutive_triggers,
            "auto_resolve": row.auto_resolve,
        }

    async def find_open(self, fingerprint: str) -> Alert | None:
        row = await AlertModel.filter(fingerprint=fingerprint).order_by("-id").first()
        return _entity(row) if row else None

    async def get(self, alert_id: int) -> Alert | None:
        row = await AlertModel.get_or_none(id=alert_id)
        return _entity(row) if row else None

    async def detail(self, alert_id: int) -> dict | None:
        row = await AlertModel.get_or_none(id=alert_id)
        return _payload(row) if row else None

    async def save(self, alert: Alert) -> None:
        values = {
            "project_id": alert.project_id, "rule_code": alert.rule_code,
            "alert_type": alert.alert_type, "level": alert.level.value,
            "title": alert.title, "message": alert.message,
            "metric_value": alert.metric_value,
            "threshold_value": alert.threshold_value, "ym": alert.ym,
            "status": alert.status.value, "fingerprint": alert.fingerprint,
            "trigger_count": alert.trigger_count,
            "first_triggered_at": alert.first_triggered_at,
            "last_triggered_at": alert.last_triggered_at,
        }
        if alert.id is None:
            row = await AlertModel.create(**values)
            alert.id = row.id
        else:
            await AlertModel.filter(id=alert.id).update(**values)

    async def record_event(self, alert: Alert, event_type: str,
                           actor_id: int | None = None, note: str = "") -> None:
        await AlertEventModel.create(
            alert_id=alert.id, event_type=event_type, actor_id=actor_id,
            note=note or None, snapshot={
                "status": alert.status.value, "level": alert.level.value,
                "metric_value": float(alert.metric_value),
                "threshold_value": float(alert.threshold_value),
            },
        )
        now = datetime.now(timezone.utc)
        updates = {}
        if event_type == "acknowledged":
            updates = {"acknowledged_by": actor_id, "acknowledged_at": now}
        elif event_type in {"resolved", "auto_resolved"}:
            updates = {"resolved_by": actor_id, "resolved_at": now,
                       "resolution_note": note or None}
        elif event_type == "ignored":
            updates = {"resolved_by": actor_id, "resolved_at": now,
                       "resolution_note": note or None}
        if updates:
            await AlertModel.filter(id=alert.id).update(**updates)

    async def add_outbox(self, alert: Alert, event_type: str) -> None:
        """Queue an outbox entry for the given alert.  Uses in-memory alert data
        plus the just-persisted auto_now fields from AlertModel."""
        row = await AlertModel.get(id=alert.id)
        await AlertOutboxModel.create(
            event_type=f"alert.{event_type}", aggregate_id=alert.id,
            project_id=alert.project_id, payload=_payload(row),
        )

    async def find(self, *, project_ids: list[int] | None, status: str,
                   level: str, pagination: Pagination) -> tuple[list, int]:
        query = AlertModel.all()
        if project_ids is not None:
            query = query.filter(project_id__in=project_ids)
        if status:
            query = query.filter(status=status)
        if level:
            query = query.filter(level=level)
        total = await query.count()
        rows = await query.order_by("-last_triggered_at", "-id").offset(
            pagination.offset
        ).limit(pagination.size)
        return [_payload(row) for row in rows], total

    async def events(self, alert_id: int, pagination: Pagination) -> tuple[list, int]:
        query = AlertEventModel.filter(alert_id=alert_id)
        total = await query.count()
        rows = await query.order_by("-id").offset(pagination.offset).limit(pagination.size)
        return [{
            "id": row.id, "alert_id": row.alert_id,
            "event_type": row.event_type, "actor_id": row.actor_id,
            "note": row.note or "", "snapshot": row.snapshot,
            "created_at": row.created_at.isoformat(),
        } for row in rows], total

    async def summary(self, project_ids: list[int] | None) -> dict:
        query = AlertModel.filter(status__in=["active", "acknowledged"])
        if project_ids is not None:
            query = query.filter(project_id__in=project_ids)
        return {
            "total": await query.count(),
            "active": await query.filter(status="active").count(),
            "acknowledged": await query.filter(status="acknowledged").count(),
            "critical": await query.filter(level="critical").count(),
            "warning": await query.filter(level="warning").count(),
        }

    async def delete_project(self, project_id: int) -> None:
        alert_ids = list(await fetch_values_list(AlertModel.filter(project_id=project_id),
            "id", flat=True,
        ))
        if alert_ids:
            await AlertEventModel.filter(alert_id__in=alert_ids).delete()
        await AlertOutboxModel.filter(project_id=project_id).delete()
        await AlertRuleStateModel.filter(project_id=project_id).delete()
        await AlertModel.filter(project_id=project_id).delete()

    async def missed_outbox(self, project_ids: list[int],
                            since: str | None) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        query = AlertOutboxModel.filter(status="sent")
        # -1 is the _ALL_PROJECTS sentinel for admins
        if -1 not in project_ids:
            query = query.filter(project_id__in=project_ids)
        if since:
            try:
                cutoff = datetime.fromisoformat(since)
            except (ValueError, TypeError):
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        query = query.filter(sent_at__gte=cutoff)
        rows = await query.order_by("id").limit(200)
        return [{"event": row.event_type, "event_id": row.id,
                 "data": row.payload, "project_id": row.project_id}
                for row in rows]


class TortoiseAlertMetricProvider(AlertMetricProvider):
    async def snapshot(self, project_id: int, ym: str | None = None) -> tuple[str | None, dict[str, Decimal]]:
        project = await Project.get_or_none(id=project_id)
        if project is None:
            return ym, {}
        batch_query = UploadBatch.filter(project_id=project_id, status="success")
        if ym:
            batch_query = batch_query.filter(ym=ym)
        batch = await batch_query.order_by("-ym", "-id").first()
        metrics = {
            "manual_warning": Decimal("1" if project.status == "warning" else "0"),
            "progress_delay": self._progress_delay(project),
            "cost_deviation_rate": Decimal("0"),
            "gross_profit_rate": Decimal("100"),
        }
        if batch:
            gross = await DataGrossProfit.filter(batch_id=batch.id).first()
            if gross:
                revenue = Decimal(_or_default(gross.actual_revenue, gross.contract_price) or 0)
                profit = Decimal(_or_default(gross.actual_profit, gross.gross_profit_net) or 0)
                metrics["gross_profit_rate"] = (
                    profit / revenue * 100 if revenue else Decimal("0")
                )
            rows = await DataDynamicIndicator.filter(batch_id=batch.id)
            indicator = sum((Decimal(row.indicator_with_tax or 0) for row in rows), Decimal("0"))
            actual = sum((Decimal(row.incurred_cost or 0) for row in rows), Decimal("0"))
            metrics["cost_deviation_rate"] = (
                (actual - indicator) / indicator * 100 if indicator else Decimal("0")
            )
        return batch.ym if batch else ym, metrics

    @staticmethod
    def _progress_delay(project) -> Decimal:
        if not project.start_date or not project.end_date:
            return Decimal("0")
        today = datetime.now().date()
        days = max((project.end_date - project.start_date).days, 1)
        elapsed = max(0, min((today - project.start_date).days, days))
        planned = Decimal(elapsed) / Decimal(days) * 100
        return max(Decimal("0"), planned - Decimal(project.progress or 0))
