from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import UserId, RoleId
from contexts.auth.domain.user import User
from contexts.auth.domain.role import Role


class UserRepository(Repository):
    @abstractmethod
    async def next_id(self) -> UserId: ...
    @abstractmethod
    async def save(self, user: User) -> None: ...
    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> User | None: ...
    @abstractmethod
    async def find_by_username(self, username: str) -> User | None: ...
    @abstractmethod
    async def get_permissions(self, user_id: UserId) -> set[str]: ...


class RoleRepository(Repository):
    @abstractmethod
    async def find_by_id(self, role_id: RoleId) -> Role | None: ...
    @abstractmethod
    async def find_all(self) -> list[Role]: ...
    @abstractmethod
    async def find_by_code(self, code: str) -> Role | None: ...
