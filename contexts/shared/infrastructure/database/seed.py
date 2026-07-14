from __future__ import annotations

# Seed default permissions, roles, and admin user on first startup.

from collections.abc import Callable

from tortoise.exceptions import IntegrityError
from tortoise.transactions import atomic

from contexts.auth.infrastructure.tables import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from contexts.shared.infrastructure.config import Settings


PERMISSIONS = [
    ("project:create", "创建项目"),
    ("project:view", "查看项目"),
    ("data:upload", "数据上传"),
    ("data:view", "数据查看"),
    ("data:delete", "数据删除"),
    ("data:export", "数据导出"),
    ("template:manage", "模板管理"),
    ("user:manage", "用户管理"),
    ("admin:roles", "角色权限管理"),
]

ROLES = {
    "admin": [
        "project:create",
        "project:view",
        "data:upload",
        "data:view",
        "data:delete",
        "data:export",
        "template:manage",
        "user:manage",
        "admin:roles",
    ],
    "manager": ["project:view", "data:upload", "data:view", "data:export"],
    "viewer": ["project:view", "data:view"],
}


async def seed_defaults(password_hasher: Callable[[str], str], settings: Settings):
    admin_password = settings.admin.default_password
    if settings.app.env != "local" and not admin_password:
        raise ValueError("DEFAULT_ADMIN_PASSWORD is required outside local environment")
    admin_password = admin_password or "admin123"
    await _do_seed(admin_password, password_hasher)


@atomic()
async def _do_seed(admin_password: str, password_hasher: Callable[[str], str]):
    for code, name in PERMISSIONS:
        await _ensure(Permission, {"code": code}, {"name": name})

    for code in ROLES:
        await _ensure(Role, {"code": code}, {"name": code})

    for role_code, perm_codes in ROLES.items():
        role = await Role.get(code=role_code)
        for perm_code in perm_codes:
            perm = await Permission.get(code=perm_code)
            await _ensure(
                RolePermission,
                {"role_id": role.id, "permission_id": perm.id},
                {},
            )

    admin = await _ensure(
        User,
        {"username": "admin"},
        {
            "password": password_hasher(admin_password),
            "real_name": "系统管理员",
        },
    )
    admin_role = await Role.get(code="admin")
    await _ensure(
        UserRole,
        {"user_id": admin.id, "role_id": admin_role.id},
        {},
    )


async def _ensure(model, lookup: dict, defaults: dict):
    found = await model.get_or_none(**lookup)
    if found is not None:
        return found
    try:
        return await model.create(**lookup, **defaults)
    except IntegrityError:
        return await model.get(**lookup)
