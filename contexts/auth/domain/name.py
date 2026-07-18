"""Name value object — encapsulates non-empty trimmed string validation."""

from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Name(ValueObject):
    """A validated display name. Must not be empty."""

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip()
        object.__setattr__(self, "value", v)
        if not v:
            raise ValidationError("name must not be empty")

    def __str__(self) -> str:
        return self.value
