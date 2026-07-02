from __future__ import annotations

from collections.abc import Callable

from contexts.auth.domain.repositories import RoleRepository
from contexts.auth.domain.role import PermissionRef, Role
from contexts.shared.domain.exceptions import (
    ConflictError,
    NotFoundError,
)
from contexts.shared.domain.identifiers import RoleId, UserId
from contexts.shared.domain.unit_of_work import UnitOfWork


class RoleApplicationService:
    def __init__(
        self, repo: RoleRepository, uow_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._repo = repo
        self._uow_factory = uow_factory

    # ── role CRUD ─────────────────────────────────────────────────

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
        async with self._uow_factory() as uow:
            await self._repo.save(role)
            await uow.commit()
        if role.id is None:
            raise RuntimeError("role repository did not assign an id")
        return self._to_dict(role)

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
        async with self._uow_factory() as uow:
            await self._repo.save(role)
            await uow.commit()
        return self._to_dict(role)

    async def delete(self, role_id: int) -> None:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        async with self._uow_factory() as uow:
            await self._repo.delete(RoleId(role_id))
            await uow.commit()

    async def get(self, role_id: int) -> dict:
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        return self._to_dict(role)

    async def list_all(self) -> list[dict]:
        roles = await self._repo.find_all()
        return [self._to_dict(r) for r in roles]

    # ── user-role assignment ──────────────────────────────────────

    async def assign_to_user(self, user_id: int, role_id: int) -> None:
        # Verify both exist
        role = await self._repo.find_by_id(RoleId(role_id))
        if role is None:
            raise NotFoundError(f"role {role_id} not found")
        async with self._uow_factory() as uow:
            await self._repo.assign_to_user(UserId(user_id), RoleId(role_id))
            await uow.commit()

    async def remove_from_user(self, user_id: int, role_id: int) -> None:
        async with self._uow_factory() as uow:
            await self._repo.remove_from_user(UserId(user_id), RoleId(role_id))
            await uow.commit()

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
