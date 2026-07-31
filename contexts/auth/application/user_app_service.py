from __future__ import annotations

import contextlib
import secrets
from typing import Any, cast

from contexts.auth.domain.password import Password
from contexts.auth.domain.ports import PasswordHasher
from contexts.auth.domain.repositories import UserRepository
from contexts.auth.domain.user import User
from contexts.shared.application.transaction import (
    TransactionalService,
    TransactionManager,
    transactional,
)
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.domain.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from contexts.shared.domain.identifiers import UserId
from contexts.shared.domain.pagination import Pagination


class UserApplicationService(TransactionalService):
    """Application service for the personnel-management view."""

    def __init__(
        self,
        users: UserRepository,
        password_hasher: PasswordHasher | None = None,
        event_publisher: EventPublisher | None = None,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        super().__init__(transaction_manager)
        self._users = users
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher

    async def list_all(
        self,
        *,
        keyword: str = "",
        pagination: Pagination,
    ) -> dict:
        keyword = keyword.strip()
        users, total = await self._users.list_all(
            keyword=keyword,
            offset=pagination.offset,
            limit=pagination.size,
        )
        user_ids = [cast(UserId, user.id) for user in users if user.id]
        if hasattr(self._users, "list_projects_for_users"):
            project_map = await self._users.list_projects_for_users(user_ids)
        else:  # compatibility for lightweight external repository adapters
            project_map = {user_id.value: await self._users.list_projects(user_id) for user_id in user_ids}
        result = []
        for index, user in enumerate(users, start=pagination.offset + 1):
            projects = (
                cast(list[dict[str, Any]], cast(object, project_map.get(user.id.value, [])))
                if user.id
                else []
            )
            base = self._serialize(user, projects)
            base["serial_number"] = index
            base["main_projects"] = [p for p in projects if p["is_primary"]]
            base["project_permission_overview"] = [
                {"id": p["id"], "code": p["code"], "name": p["name"]} for p in projects if p["is_primary"]
            ]
            base["project_permission_summary"] = {
                "manager": sum(
                    p.get("role", "manager" if p.get("is_primary") else "viewer") == "manager" for p in projects
                ),
                "viewer": sum(
                    p.get("role", "manager" if p.get("is_primary") else "viewer") == "viewer" for p in projects
                ),
            }
            result.append(base)
        return {
            "users": result,
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def get(self, user_id: int) -> dict:
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        projects = await self._users.list_projects(UserId(user_id))
        return self._serialize(user, projects)

    @transactional
    async def create(
        self,
        *,
        username: str,
        password: str,
        real_name: str = "",
        email: str = "",
        phone: str = "",
        department: str = "",
        is_admin: bool = False,
    ) -> dict:
        username = username.strip() or email.strip()
        generated_password = not password
        if not username:
            raise ValidationError("username or email is required")
        if generated_password:
            password = secrets.token_urlsafe(12)
        if await self._users.find_by_username(username):
            raise ConflictError("username already exists")
        if self._password_hasher is None:
            raise RuntimeError("password hasher is not configured")
        user = User.create(
            None,
            username,
            self._password_hasher.hash(str(Password(password))),
            real_name,
            email,
            phone,
            department,
        )
        await self._users.save(user)
        if user.id is None:
            raise RuntimeError("user repository did not assign an id")
        persisted_user_id = user.id
        with contextlib.suppress(NotImplementedError):
            await self._users.set_system_role(
                persisted_user_id,
                "admin" if is_admin else "viewer",
            )
        await self._publish_events(user)
        result = await self.get(persisted_user_id.value)
        if generated_password:
            # Returned once so a real frontend can display/copy it securely.
            result["temporary_password"] = password
        return result

    @transactional
    async def update(self, user_id: int, **values) -> dict:
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        if self._password_hasher is None:
            raise RuntimeError("password hasher is not configured")
        is_admin = values.pop("is_admin", None)
        user.update_profile(**values)
        await self._users.save(user)
        if is_admin is not None:
            with contextlib.suppress(NotImplementedError):
                await self._users.set_system_role(
                    UserId(user_id),
                    "admin" if is_admin else "viewer",
                )
        await self._publish_events(user)
        return await self.get(user_id)

    @transactional
    async def delete(self, user_id: int) -> None:
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        user.mark_deleted()
        await self._users.delete(UserId(user_id))
        await self._publish_events(user)

    @transactional
    async def reset_password(self, user_id: int, password: str) -> None:
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        if self._password_hasher is None:
            raise RuntimeError("password hasher is not configured")
        user.reset_password(self._password_hasher.hash(str(Password(password))))
        await self._users.save(user)
        await self._publish_events(user)

    async def project_permissions(self, user_id: int) -> dict:
        if await self._users.find_by_id(UserId(user_id)) is None:
            raise NotFoundError(f"user {user_id} not found")
        return {
            "user_id": user_id,
            "permissions": await self._users.list_projects(UserId(user_id)),
        }

    @transactional
    async def set_project_permissions(self, user_id: int, permissions: list[dict]) -> dict:
        allowed = {"manager", "viewer", "none"}
        if any("project_id" not in item or item.get("role") not in allowed for item in permissions):
            raise ValidationError("each permission requires project_id and role manager, viewer or none")
        await self._users.set_project_permissions(UserId(user_id), permissions)
        user = await self._users.find_by_id(UserId(user_id))
        if user:
            await self._publish_events(user)
        return await self.project_permissions(user_id)

    async def _publish_events(self, user: User) -> None:
        if self._event_publisher:
            events = user.pull_events()
            if events:
                await self._event_publisher.publish(events)

    @staticmethod
    def _serialize(user: User, projects: list[dict]) -> dict:
        return {
            "id": user.id.value if user.id else None,
            "username": user.username,
            "real_name": user.real_name,
            "email": user.email,
            "phone": user.phone,
            "department": user.department,
            "is_active": user.is_active,
            "system_roles": [{"id": r.role_id, "code": r.code, "name": r.name} for r in user.roles],
            "is_admin": any(r.code == "admin" for r in user.roles),
            "projects": projects,
        }
