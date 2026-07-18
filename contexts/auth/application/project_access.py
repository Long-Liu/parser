from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.shared.domain.exceptions import AuthorizationError, NotFoundError
from contexts.shared.domain.identifiers import UserId


class ProjectAccessRepository(ABC):
    @abstractmethod
    async def membership_role(self, user_id: int, project_id: int) -> str | None: ...

    @abstractmethod
    async def project_for_batch(self, batch_id: int) -> int | None: ...

    @abstractmethod
    async def project_for_data_row(self, template_id: str, row_id: int) -> int | None: ...

    @abstractmethod
    async def projects_for_user(self, user_id: int) -> list[int]: ...


class ProjectAccessPolicy:
    """Enforces permissions that are scoped to one project."""

    #: Permissions that bypass project/batch scope checks entirely.
    ELEVATED_PERMISSIONS = frozenset({"admin:roles", "user:manage"})

    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    @classmethod
    def has_elevated_permission(cls, permissions) -> bool:
        """True when the permission set may skip project/batch scope checks."""
        return bool(cls.ELEVATED_PERMISSIONS & set(permissions or ()))

    async def require(
        self, user_id: UserId, project_id: int, allowed_roles: set[str] | None = None,
    ) -> None:
        role = await self._repository.membership_role(user_id.value, project_id)
        if role is None:
            raise AuthorizationError(f"no access to project {project_id}")
        if allowed_roles and role not in allowed_roles:
            raise AuthorizationError(
                f"project role {role!r} cannot perform this operation"
            )

    async def require_batch(
        self, user_id: UserId, batch_id: int, allowed_roles: set[str] | None = None,
    ) -> int:
        project_id = await self._repository.project_for_batch(batch_id)
        if project_id is None:
            raise NotFoundError(f"batch {batch_id} not found")
        await self.require(user_id, project_id, allowed_roles)
        return project_id

    async def require_data_row(
        self, user_id: UserId, template_id: str, row_id: int,
        allowed_roles: set[str] | None = None,
    ) -> int:
        project_id = await self._repository.project_for_data_row(template_id, row_id)
        if project_id is None:
            raise NotFoundError(f"row {row_id} not found in {template_id}")
        await self.require(user_id, project_id, allowed_roles)
        return project_id

    async def accessible_project_ids(self, user_id: UserId) -> list[int]:
        return await self._repository.projects_for_user(user_id.value)
