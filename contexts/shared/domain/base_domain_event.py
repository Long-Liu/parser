from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.  aggregate_id is optional — some events
    fire before persistence assigns the real id (e.g. ParseJobFailed during upload)."""
    aggregate_id: object | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
