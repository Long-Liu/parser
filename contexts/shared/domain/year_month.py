from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class YearMonth(ValueObject):
    year: int
    month: int

    def __post_init__(self) -> None:
        if self.month < 1 or self.month > 12:
            raise ValidationError(f"Month must be 1-12, got {self.month}")
        if self.year < 2000 or self.year > 2100:
            raise ValidationError(f"Year out of range: {self.year}")

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @classmethod
    def parse(cls, value: str) -> YearMonth:
        parts = value.strip().split("-")
        if len(parts) != 2:
            raise ValidationError(f"Invalid YearMonth format: {value}")
        return cls(year=int(parts[0]), month=int(parts[1]))


def _demo():
    assert YearMonth.parse("2025-06") == YearMonth(2025, 6)
    try:
        YearMonth(2025, 13)
        assert False, "should reject month 13"
    except ValidationError:
        pass
    print("year_month: OK")


if __name__ == "__main__":
    _demo()
