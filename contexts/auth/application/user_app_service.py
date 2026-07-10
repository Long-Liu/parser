from __future__ import annotations

from contexts.auth.domain.repositories import UserRepository


class UserApplicationService:
    """Application service for the personnel-management view."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def list_all(self) -> list[dict]:
        result = []
        for index, user in enumerate(await self._users.list_all(), start=1):
            projects = await self._users.list_projects(user.id) if user.id else []
            result.append({
                "serial_number": index,
                "id": user.id.value if user.id else None,
                "username": user.username,
                "real_name": user.real_name,
                "email": user.email,
                "department": user.department,
                "system_roles": [
                    {"id": role.role_id, "code": role.code, "name": role.name}
                    for role in user.roles
                ],
                "projects": projects,
                "main_projects": [p for p in projects if p["is_primary"]],
                "project_permission_overview": [
                    {"id": p["id"], "code": p["code"], "name": p["name"]}
                    for p in projects if p["is_primary"]
                ],
                "is_active": user.is_active,
            })
        return result
