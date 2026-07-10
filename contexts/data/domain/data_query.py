from __future__ import annotations

from dataclasses import dataclass, field

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Pagination(ValueObject):
    page: int
    size: int
    total: int = 0

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValidationError("page must be at least 1")
        if not 1 <= self.size <= 1000:
            raise ValidationError("size must be between 1 and 1000")

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
