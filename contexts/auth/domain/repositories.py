from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from contexts.auth.domain.role import Role
from contexts.auth.domain.user import User
from contexts.shared.domain.identifiers import RoleId, UserId


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


class TokenRevocationRepository(ABC):
    """Blacklist store for revoked JWTs.

    Two revocation granularities share one store (see the Tortoise impl):
    - single token, keyed by its ``jti`` claim (logout);
    - user-wide marker, revoking every token whose ``iat`` is at or before
      the marker's ``revoked_at`` (password change — covers the current
      token as well, so no separate jti entry is needed there).
    Entries become useless once all covered tokens have expired; ``expires_at``
    records that horizon so implementations can purge lazily.
    """

    @abstractmethod
    async def revoke(self, *, jti: str, user_id: UserId, expires_at: datetime) -> None: ...

    @abstractmethod
    async def revoke_all_for_user(self, *, user_id: UserId, expires_at: datetime) -> None: ...

    @abstractmethod
    async def is_revoked(self, *, jti: str | None, user_id: UserId,
                         issued_at: float | None) -> bool: ...
