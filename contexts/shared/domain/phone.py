"""Phone value object — encapsulates format validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError

_PHONE_RE = re.compile(r"^\+?[\d \-()]{5,20}$")


@dataclass(frozen=True)
class Phone(ValueObject):
    """A validated phone number.  Empty string is allowed (not required)."""

    value: str = ""

    def __post_init__(self) -> None:
        v = self.value.strip()
        object.__setattr__(self, "value", v)
        if v and not _PHONE_RE.match(v):
            raise ValidationError(f"invalid phone: {v!r}")

    def __str__(self) -> str:
        return self.value

    def __bool__(self) -> bool:
        return bool(self.value)
