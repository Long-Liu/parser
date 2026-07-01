from __future__ import annotations

from abc import ABC, abstractmethod


class AuthContext(ABC):
    @abstractmethod
    def user_id(self) -> int | None: ...
    @abstractmethod
    def permissions(self) -> set[str]: ...
    @abstractmethod
    def has_permission(self, code: str) -> bool: ...
