from __future__ import annotations

from contexts.shared.application.transaction import transactional

from contexts.auth.domain.repositories import UserRepository
from contexts.auth.domain.user import User
from contexts.auth.application.security import PasswordHasher
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.domain.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from contexts.shared.domain.identifiers import UserId
from contexts.shared.domain.pagination import Pagination


class UserApplicationService:
    """Application service for the personnel-management view."""

    MIN_PASSWORD_LENGTH = 8

    def __init__(
        self,
        users: UserRepository,
        password_hasher: PasswordHasher | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._users = users
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher

    async def list_all(
        self, *, keyword: str = "", page: int = 1, size: int = 20,
    ) -> dict:
        pagination = Pagination(page=page, size=size, max_size=100)
        keyword = keyword.strip()
        users, total = await self._users.list_all(
            keyword=keyword,
            offset=pagination.offset,
            limit=pagination.size,
        )
        user_ids = [user.id for user in users if user.id]
        if hasattr(self._users, "list_projects_for_users"):
            project_map = await self._users.list_projects_for_users(user_ids)
        else:  # compatibility for lightweight external repository adapters
            project_map = {
                user_id.value: await self._users.list_projects(user_id)
                for user_id in user_ids
            }
        result = []
        for index, user in enumerate(users, start=pagination.offset + 1):
            projects = project_map.get(user.id.value, []) if user.id else []
            base = self._serialize(user, projects)
            base["serial_number"] = index
            base["main_projects"] = [p for p in projects if p["is_primary"]]
            base["project_permission_overview"] = [
                {"id": p["id"], "code": p["code"], "name": p["name"]}
                for p in projects
                if p["is_primary"]
            ]
            result.append(base)
        return {
            "users": result,
            "pagination": {"page": page, "size": size, "total": total},
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
    ) -> dict:
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise ValidationError("password must contain at least 8 characters")
        if await self._users.find_by_username(username):
            raise ConflictError("username already exists")
        if self._password_hasher is None:
            raise RuntimeError("password hasher is not configured")
        user = User.create(
            None,
            username,
            self._password_hasher.hash(password),
            real_name,
            email,
            phone,
            department,
        )
        await self._users.save(user)
        await self._publish_events(user)
        return await self.get(user.id.value)

    @transactional
    async def update(self, user_id: int, **values) -> dict:
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        if self._password_hasher is None:
            raise RuntimeError("password hasher is not configured")
        user.update_profile(**values)
        await self._users.save(user)
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
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise ValidationError("password must contain at least 8 characters")
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        user.reset_password(self._password_hasher.hash(password))
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
    async def set_project_permissions(
        self, user_id: int, permissions: list[dict]
    ) -> dict:
        allowed = {"manager", "viewer", "none"}
        if any(
            "project_id" not in item or item.get("role") not in allowed
            for item in permissions
        ):
            raise ValidationError(
                "each permission requires project_id and role manager, viewer or none"
            )
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
            "system_roles": [
                {"id": r.role_id, "code": r.code, "name": r.name} for r in user.roles
            ],
            "projects": projects,
        }
