"""Password value object — encapsulates cleartext password validation."""

from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError

MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class Password(ValueObject):
    """A validated cleartext password. Must meet minimum length requirement."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) < MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"password must contain at least {MIN_PASSWORD_LENGTH} characters"
            )

    def __str__(self) -> str:
        return self.value
