from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

IdType = TypeVar("IdType")


# noqa on UP046: PEP 695 syntax requires Python 3.12+, but the project venv
# currently runs Python 3.11, so the legacy Generic[IdType] form must stay.
class Entity(Generic[IdType], ABC):  # noqa: UP046
    """Domain entity base. Equality by identity (id), not attributes.

    Type parameter IdType specifies the identity type, e.g. Entity[int], Entity[UserId].
    """
    id: IdType | None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        if self.id is None:
            return object.__hash__(self)
        return hash(self.id)
