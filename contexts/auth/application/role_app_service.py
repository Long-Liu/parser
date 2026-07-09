from __future__ import annotations

from contexts.auth.domain.repositories import RoleRepository
from contexts.auth.domain.role import PermissionRef, Role
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.domain.exceptions import (
    ConflictError,
    NotFoundError,
)
from contexts.shared.domain.identifiers import RoleId, UserId
from tortoise.transactions import atomic


class RoleApplicationService:
    def __init__(
        self, repo: RoleRepository,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._repo = repo
        self._event_publisher = event_publisher

    # ── role CRUD ─────────────────────────────────────────────────

    @atomic()
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
        return self._to_dict(role)

    @atomic()
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
        return self._to_dict(role)

    @atomic()
    async def delete(self, role_id: int) -> None:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        await self._repo.delete(RoleId(role_id))

    async def get(self, role_id: int) -> dict:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        return self._to_dict(role)

    async def list_all(self) -> list[dict]:
        roles = await self._repo.find_all()
        return [self._to_dict(r) for r in roles]

    # ── user-role assignment ──────────────────────────────────────

    @atomic()
    async def assign_to_user(self, user_id: int, role_id: int) -> None:
        # Verify both exist
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        await self._repo.assign_to_user(UserId(user_id), RoleId(role_id))

    @atomic()
    async def remove_from_user(self, user_id: int, role_id: int) -> None:
        await self._repo.remove_from_user(UserId(user_id), RoleId(role_id))

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _to_dict(role: Role) -> dict:
        return {
            "id": role.id,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "permissions": [
                {"code": p.code, "name": p.name} for p in role.permissions
            ],
        }
