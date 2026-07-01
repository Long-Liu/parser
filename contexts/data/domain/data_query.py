from __future__ import annotations

from dataclasses import dataclass, field

from contexts.shared.domain.base_value_object import ValueObject


@dataclass(frozen=True)
class Pagination(ValueObject):
    page: int
    size: int
    total: int = 0

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(frozen=True)
class FilterCriterion(ValueObject):
    field: str
    operator: str
    value: object


@dataclass(frozen=True)
class DataRow(ValueObject):
    fields: dict = field(default_factory=dict)
    monthly_data: dict | None = None
    batch_ref: dict | None = None
