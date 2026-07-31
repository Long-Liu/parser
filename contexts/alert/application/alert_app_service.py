from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from contexts.alert.domain.alert import Alert, AlertRule, AlertStatus
from contexts.alert.domain.repositories import (
    AlertMetricProvider,
    AlertPushDispatcher,
    AlertRepository,
)
from contexts.shared.application.transaction import (
    TransactionalService,
    TransactionManager,
    defer_after_commit,
    transactional,
)
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination

logger = logging.getLogger("parser.alert")


class AlertApplicationService(TransactionalService):
    def __init__(
        self,
        repository: AlertRepository,
        metrics: AlertMetricProvider,
        dispatcher: AlertPushDispatcher,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        super().__init__(transaction_manager)
        self._repository = repository
        self._metrics = metrics
        self._dispatcher = dispatcher
        # 分发任务登记：done 后自动移除，避免停机时残留不可追踪的后台任务。
        self._dispatch_tasks: set[asyncio.Task] = set()

    @transactional
    async def evaluate(self, project_id: int, ym: str | None = None) -> dict:
        period, values = await self._metrics.snapshot(project_id, ym)
        if not values:
            raise NotFoundError(f"project {project_id} not found")
        triggered = resolved = 0
        evaluations: list[tuple[AlertRule, Decimal, str, str, bool]] = []
        for rule in await self._repository.rules():
            value = values.get(rule.metric)
            if value is None:
                continue
            scope = (period or "current") if rule.metric in {"cost_deviation_rate", "gross_profit_rate"} else "current"
            fingerprint = f"{project_id}:{rule.code}:{scope}"
            evaluations.append((rule, value, scope, fingerprint, rule.matches(value)))
        checks = [(rule.code, scope, matched, fingerprint) for rule, _, scope, fingerprint, matched in evaluations]
        states: dict[str, tuple[Alert | None, int]]
        if hasattr(self._repository, "evaluation_states"):
            states = await self._repository.evaluation_states(project_id, checks)
        else:
            # Backward compatibility for duck-typed adapters.
            states = {}
            for rule_code, scope, matched, fingerprint in checks:
                existing = await self._repository.find_open(fingerprint)
                consecutive = await self._repository.register_match(project_id, rule_code, scope, matched)
                states[fingerprint] = (existing, consecutive)
        for rule, value, _, fingerprint, matched in evaluations:
            existing, consecutive = states[fingerprint]
            t, r = await self._evaluate_rule(
                rule,
                existing,
                consecutive,
                matched,
                project_id,
                period,
                value,
                fingerprint,
            )
            triggered += t
            resolved += r
        self._schedule_dispatch()
        return {"project_id": project_id, "ym": period, "triggered": triggered, "resolved": resolved}

    async def _evaluate_rule(
        self,
        rule: AlertRule,
        existing: Alert | None,
        consecutive: int,
        matched: bool,
        project_id: int,
        period: str | None,
        value: Decimal,
        fingerprint: str,
    ) -> tuple[int, int]:
        if matched and consecutive >= rule.consecutive_triggers:
            return await self._trigger_alert(rule, existing, project_id, period, value, fingerprint), 0
        if existing is not None and existing.open and rule.auto_resolve:
            return 0, await self._auto_resolve_alert(existing)
        return 0, 0

    async def _trigger_alert(
        self,
        rule: AlertRule,
        existing: Alert | None,
        project_id: int,
        period: str | None,
        value: Decimal,
        fingerprint: str,
    ) -> int:
        if existing is not None and existing.status == AlertStatus.IGNORED:
            return 0
        message = self._message(rule.name, value, rule.threshold)
        if existing is not None:
            event_type = existing.retrigger(value, rule.level, message)
            alert = existing
        else:
            alert = Alert(
                alert_id=None,
                project_id=project_id,
                rule_code=rule.code,
                alert_type=rule.metric,
                level=rule.level,
                title=rule.name,
                message=message,
                metric_value=value,
                threshold_value=rule.threshold,
                fingerprint=fingerprint,
                ym=period,
            )
            event_type = "triggered"
        await self._repository.save(alert)
        await self._repository.record_event(alert, event_type)
        await self._repository.add_outbox(alert, event_type)
        return 1

    async def _auto_resolve_alert(self, existing: Alert) -> int:
        existing.resolve()
        await self._repository.save(existing)
        await self._repository.record_event(existing, "auto_resolved", note="指标已恢复正常")
        await self._repository.add_outbox(existing, "resolved")
        return 1

    async def find(
        self, *, project_ids: list[int] | None, status: str = "", level: str = "", pagination: Pagination
    ) -> dict:
        if status and status not in {item.value for item in AlertStatus}:
            raise ValidationError("invalid alert status")
        rows, total = await self._repository.find(
            project_ids=project_ids,
            status=status,
            level=level,
            pagination=pagination,
        )
        return {
            "alerts": rows,
            "pagination": {
                "page": pagination.page,
                "size": pagination.size,
                "total": total,
            },
        }

    async def summary(self, project_ids: list[int] | None) -> dict:
        return await self._repository.summary(project_ids)

    async def rules(self, pagination: Pagination) -> dict:
        rows, total = await self._repository.rule_records(pagination)
        return {
            "rules": rows,
            "pagination": {
                "page": pagination.page,
                "size": pagination.size,
                "total": total,
            },
        }

    @transactional
    async def update_rule(self, rule_id: int, values: dict) -> dict:
        allowed = {"threshold", "level", "enabled", "consecutive_triggers", "auto_resolve"}
        unknown = set(values) - allowed
        if unknown:
            raise ValidationError(f"unsupported rule fields: {sorted(unknown)}")
        clean = dict(values)
        if "threshold" in clean:
            clean["threshold"] = Decimal(str(clean["threshold"]))
        if "level" in clean and clean["level"] not in {"info", "warning", "critical"}:
            raise ValidationError("invalid alert level")
        if "consecutive_triggers" in clean:
            clean["consecutive_triggers"] = int(clean["consecutive_triggers"])
            if clean["consecutive_triggers"] < 1:
                raise ValidationError("consecutive_triggers must be positive")
        row = await self._repository.update_rule(rule_id, clean)
        if row is None:
            raise NotFoundError(f"alert rule {rule_id} not found")
        return row

    async def get(self, alert_id: int) -> dict:
        row = await self._repository.detail(alert_id)
        if row is None:
            raise NotFoundError(f"alert {alert_id} not found")
        return row

    async def events(self, alert_id: int, pagination: Pagination) -> dict:
        await self._required(alert_id)
        rows, total = await self._repository.events(alert_id, pagination)
        return {
            "events": rows,
            "pagination": {
                "page": pagination.page,
                "size": pagination.size,
                "total": total,
            },
        }

    @transactional
    async def acknowledge(self, alert_id: int, actor_id: int, note: str = "") -> dict:
        alert = await self._required(alert_id)
        alert.acknowledge()
        await self._persist_action(alert, "acknowledged", actor_id, note)
        return await self.get(alert_id)

    @transactional
    async def resolve(self, alert_id: int, actor_id: int, note: str) -> dict:
        if not note.strip():
            raise ValidationError("resolution note is required")
        alert = await self._required(alert_id)
        alert.resolve()
        await self._persist_action(alert, "resolved", actor_id, note.strip())
        return await self.get(alert_id)

    @transactional
    async def ignore(self, alert_id: int, actor_id: int, note: str) -> dict:
        if not note.strip():
            raise ValidationError("ignore reason is required")
        alert = await self._required(alert_id)
        alert.ignore()
        await self._persist_action(alert, "ignored", actor_id, note.strip())
        return await self.get(alert_id)

    async def project_id(self, alert_id: int) -> int:
        return (await self._required(alert_id)).project_id

    @transactional
    async def delete_project(self, project_id: int) -> None:
        await self._repository.delete_project(project_id)

    async def missed_notifications(self, project_ids: list[int], since: str | None) -> list[dict]:
        return await self._repository.missed_outbox(project_ids, since)

    async def _persist_action(self, alert: Alert, event_type: str, actor_id: int, note: str) -> None:
        await self._repository.save(alert)
        await self._repository.record_event(alert, event_type, actor_id, note)
        await self._repository.add_outbox(alert, event_type)
        self._schedule_dispatch()

    async def _required(self, alert_id: int) -> Alert:
        alert = await self._repository.get(alert_id)
        if alert is None:
            raise NotFoundError(f"alert {alert_id} not found")
        return alert

    def _schedule_dispatch(self) -> None:
        # 推送始终在后台任务执行：请求协程只提交事务，不串行 await 各 socket。
        # 事务内 defer 到 after-commit（提交后再读 outbox），否则立即调度。
        if not defer_after_commit(self._spawn_dispatch_task):
            self._track_dispatch(asyncio.create_task(self._safe_dispatch()))

    async def _spawn_dispatch_task(self) -> None:
        # defer_after_commit 的回调会被事务包装器 await，必须保持 awaitable。
        self._track_dispatch(asyncio.create_task(self._safe_dispatch()))

    def _track_dispatch(self, task: asyncio.Task) -> None:
        self._dispatch_tasks.add(task)
        task.add_done_callback(self._dispatch_tasks.discard)

    async def _safe_dispatch(self) -> None:
        # noinspection PyBroadException
        try:
            await self._dispatcher.dispatch_pending()
        except Exception:
            logger.exception("alert outbox dispatch failed")

    @staticmethod
    def _message(name: str, value: Decimal, threshold: Decimal) -> str:
        return f"{name}：当前值 {value.quantize(Decimal('0.01'))}，阈值 {threshold}"
