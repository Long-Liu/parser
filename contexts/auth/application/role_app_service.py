from __future__ import annotations

from contexts.shared.application.transaction import transactional

from contexts.auth.domain.repositories import RoleRepository, UserRepository
from contexts.auth.domain.role import PermissionRef, Role
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.domain.exceptions import (
    ConflictError,
    NotFoundError,
)
from contexts.shared.domain.identifiers import RoleId, UserId
from contexts.shared.domain.pagination import Pagination


class RoleApplicationService:
    def __init__(
        self,
        repo: RoleRepository,
        event_publisher: EventPublisher | None = None,
        users: UserRepository | None = None,
    ) -> None:
        self._repo = repo
        self._event_publisher = event_publisher
        self._users = users

    # ── role CRUD ─────────────────────────────────────────────────

    @transactional
    async def create(
        self, code: str, name: str, description: str = "",
        permission_codes: list[str] | None = None,
    ) -> dict:
        existing = await self._repo.find_all()
        if any(r.code == code for r in existing):
            raise ConflictError(f"role code '{code}' already exists")
        permissions = [
            PermissionRef(code=c) for c in (permission_codes or [])
        ]
        role = Role.create(code=code, name=name, description=description,
                          permissions=permissions)
        await self._repo.save(role)
        if role.id is None:
            raise RuntimeError("role repository did not assign an id")
        if self._event_publisher:
            await self._event_publisher.publish(role.pull_events())
        return self._serialize(role)

    @transactional
    async def update(
        self, role_id: int, name: str, description: str = "",
        permission_codes: list[str] | None = None,
    ) -> dict:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        role.rename(name, description)
        if permission_codes is not None:
            role.assign_permissions(
                [PermissionRef(code=c) for c in permission_codes]
            )
        await self._repo.save(role)
        if self._event_publisher:
            await self._event_publisher.publish(role.pull_events())
        return self._serialize(role)

    @transactional
    async def delete(self, role_id: int) -> None:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        await self._repo.delete(RoleId(role_id))

    async def get(self, role_id: int) -> dict:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        return self._serialize(role)

    async def list_all(self, pagination: Pagination) -> dict:
        roles = await self._repo.find_all()
        rows = roles[pagination.offset: pagination.offset + pagination.size]
        return {
            "roles": [self._serialize(r) for r in rows],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": len(roles)},
        }

    # ── user-role assignment ──────────────────────────────────────

    @transactional
    async def assign_to_user(self, user_id: int, role_id: int) -> None:
        # Verify both exist
        if self._users is None:
            raise RuntimeError("UserRepository is not configured")
        if await self._users.find_by_id(UserId(user_id)) is None:
            raise NotFoundError(f"user {user_id} not found")
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        await self._repo.assign_to_user(UserId(user_id), RoleId(role_id))

    @transactional
    async def remove_from_user(self, user_id: int, role_id: int) -> None:
        if self._users and await self._users.find_by_id(UserId(user_id)) is None:
            raise NotFoundError(f"user {user_id} not found")
        await self._repo.remove_from_user(UserId(user_id), RoleId(role_id))

    @transactional
    async def set_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        if self._users is None:
            raise RuntimeError("UserRepository is not configured")
        if await self._users.find_by_id(UserId(user_id)) is None:
            raise NotFoundError(f"user {user_id} not found")
        roles = await self._repo.find_all()
        valid_ids = {role.id.value for role in roles if role.id}
        if not set(role_ids).issubset(valid_ids):
            raise NotFoundError("one or more roles do not exist")
        for role in roles:
            rid = role.id.value if role.id else None
            if rid in role_ids:
                await self._repo.assign_to_user(UserId(user_id), RoleId(rid))
            else:
                await self._repo.remove_from_user(UserId(user_id), RoleId(rid))

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _serialize(role: Role) -> dict:
        return {
            "id": role.id.value if role.id else None,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "permissions": [{"code": p.code, "name": p.name} for p in role.permissions],
        }
