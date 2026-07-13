from __future__ import annotations

from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from contexts.auth.domain.repositories import RoleRepository, UserRepository
from contexts.auth.domain.role import PermissionRef, Role
from contexts.auth.domain.user import RoleRef, User
from contexts.auth.infrastructure.tables import (
    Permission as OrmPermission,
    Role as OrmRole,
    RolePermission,
    User as OrmUser,
    UserRole,
)
from contexts.project.infrastructure.tables import ProjectUser
from contexts.project.infrastructure.tables import Project as OrmProject
from contexts.shared.domain.identifiers import RoleId, UserId
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.infrastructure.database.queryset_helpers import (
    fetch_values,
    fetch_values_list,
)


def _user_to_entity(orm: OrmUser, roles: list[dict]) -> User:
        return User(
        user_id=UserId(orm.id),
        username=orm.username,
        password_hash=orm.password,
        real_name=orm.real_name or "",
        email=orm.email or "",
        phone=orm.phone or "",
        department=orm.department or "",
        roles=[RoleRef(role_id=r["id"], code=r["code"], name=r.get("name", "")) for r in roles],
        is_active=bool(orm.is_active),
    )


async def _load_roles(user_id: int) -> list[dict]:
    role_ids = await fetch_values_list(UserRole.filter(user_id=user_id), "role_id", flat=True)
    if not role_ids:
        return []
    return list(
        await fetch_values(OrmRole.filter(id__in=list(role_ids)), "id", "code", "name")
    )


class UserRepositoryImpl(UserRepository):
    async def save(self, user: User) -> None:
        values = {
            "username": user.username,
            "password": user.password_hash,
            "real_name": user.real_name,
            "email": user.email,
            "phone": user.phone,
            "department": user.department,
            "is_active": user.is_active,
        }
        if user.id is None:
            orm = await OrmUser.create(**values)
            user.id = UserId(orm.id)
            return

        existing = await OrmUser.get_or_none(id=user.id.value)
        if existing is None:
            orm = OrmUser(id=user.id.value, **values)
            await orm.save(force_create=True)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            await existing.save(update_fields=list(values.keys()))

    async def find_by_id(self, user_id: UserId) -> User | None:
        orm = await OrmUser.get_or_none(id=user_id.value)
        if orm is None:
            return None
        return _user_to_entity(orm, await _load_roles(orm.id))

    async def find_by_username(self, username: str) -> User | None:
        orm = await OrmUser.get_or_none(username=username)
        if orm is None:
            return None
        return _user_to_entity(orm, await _load_roles(orm.id))

    async def list_all(
        self, *, keyword: str = "", offset: int = 0, limit: int = 20,
    ) -> tuple[list[User], int]:
        query = OrmUser.all()
        if keyword:
            query = query.filter(
                Q(real_name__icontains=keyword) | Q(email__icontains=keyword)
            )

        total = await query.count()
        users = []
        for orm in await query.order_by("id").offset(offset).limit(limit):
            users.append(_user_to_entity(orm, await _load_roles(orm.id)))
        return users, total

    async def list_projects(self, user_id: UserId) -> list[dict]:
        links = await fetch_values(ProjectUser.filter(user_id=user_id.value),
            "project_id", "is_primary", "role",
        )
        if not links:
            return []
        projects = {
            p["id"]: p for p in await fetch_values(OrmProject.filter(
                id__in=[link["project_id"] for link in links],
            ), "id", "code", "name")
        }
        return [
            {**projects[link["project_id"]], "is_primary": bool(link["is_primary"]),
             "role": link["role"]}
            for link in links if link["project_id"] in projects
        ]

    async def list_projects_for_users(self, user_ids: list[UserId]) -> dict[int, list[dict]]:
        ids = [item.value for item in user_ids]
        result = {user_id: [] for user_id in ids}
        if not ids:
            return result
        links = await fetch_values(ProjectUser.filter(user_id__in=ids),
            "user_id", "project_id", "is_primary", "role",
        )
        project_ids = {link["project_id"] for link in links}
        projects = {
            row["id"]: row for row in await fetch_values(OrmProject.filter(id__in=project_ids),
                "id", "code", "name",
            )
        }
        for link in links:
            project = projects.get(link["project_id"])
            if project:
                result[int(link["user_id"])].append({
                    **project,
                    "is_primary": bool(link["is_primary"]),
                    "role": link["role"],
                })
        return result

    async def delete(self, user_id: UserId) -> None:
        await ProjectUser.filter(user_id=user_id.value).delete()
        await UserRole.filter(user_id=user_id.value).delete()
        await OrmUser.filter(id=user_id.value).delete()

    async def set_project_permissions(self, user_id: UserId,
                                      permissions: list[dict]) -> None:
        # Deduplicate by project_id — last entry wins. Validate types early.
        deduped: dict[int, str] = {}
        try:
            for item in permissions:
                deduped[int(item["project_id"])] = item.get("role", "none")
        except (ValueError, TypeError, KeyError):
            raise ValidationError("each permission requires a valid numeric project_id") from None
        existing_ids = set()
        if deduped:
            existing_ids = {row["id"] for row in await fetch_values(OrmProject.filter(
                id__in=list(deduped.keys()),
            ), "id")}
        missing = set(deduped.keys()) - existing_ids
        if missing:
            raise ValidationError(f"unknown project ids: {sorted(missing)}")
        await ProjectUser.filter(user_id=user_id.value).delete()
        for project_id, role in deduped.items():
            if role == "none":
                continue
            await ProjectUser.create(
                user_id=user_id.value,
                project_id=project_id,
                role=role,
                is_primary=role == "manager",
            )

    async def get_permissions(self, user_id: UserId) -> set[str]:
        role_ids = await fetch_values_list(UserRole.filter(user_id=user_id.value),
            "role_id", flat=True,
        )
        if not role_ids:
            return set()
        permission_ids = await fetch_values_list(RolePermission.filter(
            role_id__in=list(role_ids),
        ), "permission_id", flat=True)
        if not permission_ids:
            return set()
        codes = await fetch_values_list(OrmPermission.filter(id__in=list(permission_ids)),
            "code", flat=True,
        )
        return set(codes)


class RoleRepositoryImpl(RoleRepository):
    async def save(self, role: Role) -> None:
        values = {
            "code": role.code,
            "name": role.name,
            "description": role.description,
        }
        if role.id is None:
            orm = await OrmRole.create(**values)
            role.id = RoleId(orm.id)
        else:
            rid = role.id.value
            existing = await OrmRole.get_or_none(id=rid)
            if existing is None:
                orm = OrmRole(id=rid, **values)
                await orm.save(force_create=True)
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
                await existing.save(update_fields=list(values.keys()))
            await RolePermission.filter(role_id=rid).delete()

        for perm in role.permissions:
            perm_id = await _ensure_permission(perm.code, perm.name)
            await _ensure_role_permission(role.id.value, perm_id)

    async def find_by_id(self, role_id: RoleId) -> Role | None:
        orm = await OrmRole.get_or_none(id=role_id.value)
        if orm is None:
            return None
        perms = await _load_permissions(orm.id)
        return Role(
            role_id=RoleId(orm.id),
            code=orm.code,
            name=orm.name,
            description=orm.description or "",
            permissions=[PermissionRef(code=p.code, name=p.name) for p in perms],
        )

    async def find_all(self) -> list[Role]:
        roles = []
        for orm in await OrmRole.all():
            perms = await _load_permissions(orm.id)
            roles.append(
                Role(
                    role_id=RoleId(orm.id),
                    code=orm.code,
                    name=orm.name,
                    description=orm.description or "",
                    permissions=[
                        PermissionRef(code=p.code, name=p.name) for p in perms
                    ],
                )
            )
        return roles

    async def delete(self, role_id: RoleId) -> None:
        await RolePermission.filter(role_id=role_id.value).delete()
        await UserRole.filter(role_id=role_id.value).delete()
        await OrmRole.filter(id=role_id.value).delete()

    async def assign_to_user(self, user_id: UserId, role_id: RoleId) -> None:
        await _ensure_user_role(user_id.value, role_id.value)

    async def remove_from_user(self, user_id: UserId, role_id: RoleId) -> None:
        await UserRole.filter(
            user_id=user_id.value, role_id=role_id.value
        ).delete()


async def _ensure_permission(code: str, name: str) -> int:
    perm = await OrmPermission.get_or_none(code=code)
    if perm is not None:
        return perm.id
    try:
        perm = await OrmPermission.create(code=code, name=name)
    except IntegrityError:
        perm = await OrmPermission.get(code=code)
    return perm.id


async def _ensure_role_permission(role_id: int, permission_id: int) -> None:
    if await RolePermission.get_or_none(
        role_id=role_id, permission_id=permission_id
    ):
        return
    try:
        await RolePermission.create(role_id=role_id, permission_id=permission_id)
    except IntegrityError:
        return


async def _ensure_user_role(user_id: int, role_id: int) -> None:
    if await UserRole.get_or_none(user_id=user_id, role_id=role_id):
        return
    try:
        await UserRole.create(user_id=user_id, role_id=role_id)
    except IntegrityError:
        return


async def _load_permissions(role_id: int) -> list[OrmPermission]:
    permission_ids = await fetch_values_list(RolePermission.filter(role_id=role_id),
        "permission_id", flat=True,
    )
    if not permission_ids:
        return []
    return list(await OrmPermission.filter(id__in=list(permission_ids)))
