from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contexts.shared.domain.base_value_object import ValueObject


@dataclass(frozen=True)
class FilterCriterion(ValueObject):
    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class DataRow(ValueObject):
    fields: dict = field(default_factory=dict)
    monthly_data: dict | None = None
    batch_ref: dict | None = None
