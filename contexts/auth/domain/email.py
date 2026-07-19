"""Email value object — encapsulates format validation."""

from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Email(ValueObject):
    """A validated email address.  Empty string is allowed (not required)."""

    value: str = ""

    def __post_init__(self) -> None:
        v = self.value.strip()
        object.__setattr__(self, "value", v)
        if v and "@" not in v:
            raise ValidationError(f"invalid email: {v!r}")

    def __str__(self) -> str:
        return self.value

    def __bool__(self) -> bool:
        return bool(self.value)
