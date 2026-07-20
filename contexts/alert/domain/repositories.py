from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from contexts.alert.domain.alert import Alert, AlertRule
from contexts.shared.domain.pagination import Pagination


class AlertRepository(ABC):
    @abstractmethod
    async def rules(self) -> list[AlertRule]: ...
    @abstractmethod
    async def rule_records(self, pagination: Pagination) -> tuple[list[dict], int]: ...
    @abstractmethod
    async def update_rule(self, rule_id: int, values: dict) -> dict | None: ...
    @abstractmethod
    async def register_match(self, project_id: int, rule_code: str,
                             scope: str, matched: bool) -> int: ...
    @abstractmethod
    async def find_open(self, fingerprint: str) -> Alert | None: ...
    @abstractmethod
    async def get(self, alert_id: int) -> Alert | None: ...
    @abstractmethod
    async def detail(self, alert_id: int) -> dict | None: ...
    @abstractmethod
    async def save(self, alert: Alert) -> None: ...

    # Infrastructure convenience — not abstract. Default no-ops so test fakes
    # don't need to implement event/outbox persistence.
    async def record_event(self, alert: Alert, event_type: str,  # noqa: B027
                           actor_id: int | None = None, note: str = "") -> None:
        pass

    async def add_outbox(self, alert: Alert, event_type: str) -> None:  # noqa: B027
        pass
    @abstractmethod
    async def find(self, *, project_ids: list[int] | None, status: str,
                   level: str, pagination: Pagination) -> tuple[list[dict], int]: ...
    @abstractmethod
    async def events(self, alert_id: int, pagination: Pagination) -> tuple[list[dict], int]: ...
    @abstractmethod
    async def summary(self, project_ids: list[int] | None) -> dict: ...
    @abstractmethod
    async def delete_project(self, project_id: int) -> None: ...

    async def missed_outbox(self, project_ids: list[int],
                            since: str | None) -> list[dict]:
        return []


class AlertMetricProvider(ABC):
    @abstractmethod
    async def snapshot(self, project_id: int, ym: str | None = None) -> tuple[str | None, dict[str, Decimal]]: ...


class AlertPushDispatcher(ABC):
    @abstractmethod
    async def dispatch_pending(self) -> None: ...
