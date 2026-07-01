from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    aggregate_id: object
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
