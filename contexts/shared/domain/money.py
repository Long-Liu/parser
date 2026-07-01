from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Money(ValueObject):
    """Money in cents (int) to avoid floating-point errors."""
    cents: int
    currency: str = "CNY"

    def __post_init__(self) -> None:
        if self.currency not in ("CNY", "USD", "EUR"):
            raise ValidationError(f"Unsupported currency: {self.currency}")

    @classmethod
    def from_yuan(cls, yuan: float, currency: str = "CNY") -> "Money":
        return cls(cents=round(yuan * 100), currency=currency)

    def to_yuan(self) -> float:
        return self.cents / 100.0

    def __str__(self) -> str:
        return f"{self.currency} {self.cents / 100:,.2f}"

    def __neg__(self) -> "Money":
        return Money(cents=-self.cents, currency=self.currency)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValidationError("Cannot add Money with different currencies")
        return Money(cents=self.cents + other.cents, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        return self + (-other)


def _demo():
    a = Money(10000)  # 100.00 CNY
    b = Money(5000)   # 50.00 CNY
    assert a + b == Money(15000)
    assert a - b == Money(5000)
    assert str(a) == "CNY 100.00"
    assert Money.from_yuan(123.45) == Money(12345)
    assert Money.from_yuan(123.456).to_yuan() == 123.46  # rounded
    try:
        Money(100, "JPY")
        assert False, "should reject unsupported currency"
    except ValidationError:
        pass
    print("money: OK")


if __name__ == "__main__":
    _demo()
