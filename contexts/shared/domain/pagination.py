from __future__ import annotations

from dataclasses import InitVar, dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Pagination(ValueObject):
    """Validated pagination request shared by bounded contexts."""

    page: int
    size: int
    max_size: InitVar[int] = 1000

    def __post_init__(self, max_size: int) -> None:
        if self.page < 1:
            raise ValidationError("page must be at least 1")
        if not 1 <= self.size <= max_size:
            raise ValidationError(f"size must be between 1 and {max_size}")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
