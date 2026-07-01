from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Immutable value object base. Equality by all fields."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return tuple(self.__dict__.values()) == tuple(other.__dict__.values())

    def __hash__(self) -> int:
        return hash(tuple(self.__dict__.values()))


@dataclass(frozen=True)
class _DemoMoney(ValueObject):
    amount: int
    currency: str


def _demo():
    a = _DemoMoney(100, "CNY")
    b = _DemoMoney(100, "CNY")
    c = _DemoMoney(200, "CNY")
    assert a == b, "same values should be equal"
    assert a != c, "different values should not be equal"
    assert hash(a) == hash(b), "equal objects should have equal hash"
    print("base_value_object: OK")


if __name__ == "__main__":
    _demo()
