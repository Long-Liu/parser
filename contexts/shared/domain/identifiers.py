from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class _IntId(ValueObject):
    """Base for integer identifiers — validates positive, provides str()."""
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"{type(self).__name__} must be positive, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)


# ponytail: explicit types for type safety at boundaries; thin wrappers over _IntId
class UserId(_IntId): pass
class ProjectId(_IntId): pass
class JobId(_IntId): pass
class BatchId(_IntId): pass
class RoleId(_IntId): pass


@dataclass(frozen=True)
class TemplateId(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError("TemplateId must not be empty")

    def __str__(self) -> str:
        return self.value
