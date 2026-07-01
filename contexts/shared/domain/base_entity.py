from __future__ import annotations

from abc import ABC


class Entity(ABC):
    """Domain entity base. Equality by identity (id), not attributes."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        if not hasattr(self, "id") or not hasattr(other, "id"):
            raise NotImplementedError("Entity subclass must define an 'id' field")
        if self.id is None or other.id is None:  # type: ignore[attr-defined]
            return self is other
        return self.id == other.id  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        if not hasattr(self, "id"):
            raise NotImplementedError("Entity subclass must define an 'id' field")
        if self.id is None:  # type: ignore[attr-defined]
            return object.__hash__(self)
        return hash(self.id)  # type: ignore[attr-defined]


class _DemoUser(Entity):
    def __init__(self, user_id: int, name: str) -> None:
        self.id = user_id
        self.name = name


def _demo():
    a = _DemoUser(1, "Alice")
    b = _DemoUser(1, "Bob")
    c = _DemoUser(2, "Alice")
    assert a == b, "same id should be equal regardless of attributes"
    assert a != c, "different id should not be equal"
    assert hash(a) == hash(b), "equal entities should have equal hash"
    print("base_entity: OK")


if __name__ == "__main__":
    _demo()
