from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Money(ValueObject):
    amount: float
    currency: str = "CNY"

    def __post_init__(self) -> None:
        if self.currency not in ("CNY", "USD", "EUR"):
            raise ValidationError(f"Unsupported currency: {self.currency}")

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"

    def __neg__(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValidationError("Cannot add Money with different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        return self + (-other)


def _demo():
    a = Money(100, "CNY")
    b = Money(50, "CNY")
    assert a + b == Money(150, "CNY")
    assert a - b == Money(50, "CNY")
    try:
        Money(100, "JPY")
        assert False, "should reject unsupported currency"
    except ValidationError:
        pass
    print("money: OK")


if __name__ == "__main__":
    _demo()
