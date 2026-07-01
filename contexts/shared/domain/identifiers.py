from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class UserId(ValueObject):
    value: int
    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"UserId must be positive, got {self.value}")
    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class ProjectId(ValueObject):
    value: int
    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"ProjectId must be positive, got {self.value}")
    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class TemplateId(ValueObject):
    value: str
    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError("TemplateId must not be empty")
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class JobId(ValueObject):
    value: int
    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"JobId must be positive, got {self.value}")
    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class BatchId(ValueObject):
    value: int
    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"BatchId must be positive, got {self.value}")
    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class RoleId(ValueObject):
    value: int
    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"RoleId must be positive, got {self.value}")
    def __str__(self) -> str:
        return str(self.value)
