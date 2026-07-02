from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.shared.domain.identifiers import RoleId, UserId
from contexts.auth.domain.user import User
from contexts.auth.domain.role import Role


class UserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> User | None: ...

    @abstractmethod
    async def find_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_permissions(self, user_id: UserId) -> set[str]: ...


class RoleRepository(ABC):
    @abstractmethod
    async def save(self, role: Role) -> None: ...

    @abstractmethod
    async def find_by_id(self, role_id: RoleId) -> Role | None: ...

    @abstractmethod
    async def find_all(self) -> list[Role]: ...

    @abstractmethod
    async def delete(self, role_id: RoleId) -> None: ...

    @abstractmethod
    async def assign_to_user(self, user_id: UserId, role_id: RoleId) -> None: ...

    @abstractmethod
    async def remove_from_user(self, user_id: UserId, role_id: RoleId) -> None: ...
