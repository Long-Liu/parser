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
    async def list_all(
        self, *, keyword: str = "", offset: int = 0, limit: int = 20,
    ) -> tuple[list[User], int]: ...

    @abstractmethod
    async def list_projects(self, user_id: UserId) -> list[dict]: ...

    async def list_projects_for_users(self, user_ids: list[UserId]) -> dict[int, list[dict]]:
        result: dict[int, list[dict]] = {}
        for user_id in user_ids:
            result[user_id.value] = await self.list_projects(user_id)
        return result

    async def delete(self, user_id: UserId) -> None:
        raise NotImplementedError

    async def set_project_permissions(self, user_id: UserId,
                                      permissions: list[dict]) -> None:
        raise NotImplementedError

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
