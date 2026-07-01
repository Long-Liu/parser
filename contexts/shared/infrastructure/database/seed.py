"""Seed default permissions, roles, and admin user on first startup."""

import sqlalchemy as sa
from collections.abc import Callable

from contexts.shared.infrastructure.unit_of_work import transactional


PERMISSIONS = [
    ("project:create", "创建项目"),
    ("project:view", "查看项目"),
    ("data:upload", "数据上传"),
    ("data:view", "数据查看"),
    ("data:export", "数据导出"),
    ("template:manage", "模板管理"),
    ("user:manage", "用户管理"),
]

ROLES = {
    "admin": ["project:create", "project:view", "data:upload", "data:view",
              "data:export", "template:manage", "user:manage"],
    "manager": ["project:view", "data:upload", "data:view", "data:export"],
    "viewer": ["project:view", "data:view"],
}


async def seed_defaults(password_hasher: Callable[[str], str]):
    import os
    env = os.getenv("APP_ENV", "local")
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    if env != "local" and not admin_password:
        raise ValueError("DEFAULT_ADMIN_PASSWORD is required outside local environment")
    admin_password = admin_password or "admin123"
    await _do_seed(admin_password, password_hasher)


@transactional
async def _do_seed(admin_password: str, password_hasher: Callable[[str], str]):
    from contexts.shared.infrastructure.database.tables import (
        users, roles, permissions, user_roles, role_permissions,
    )
    from contexts.shared.infrastructure.unit_of_work import current_session

    def _s():
        return current_session()

    # Insert permissions
    for code, name in PERMISSIONS:
        await _s().execute(
            sa.insert(permissions).prefix_with("IGNORE").values(code=code, name=name)
        )

    # Insert roles
    for code in ROLES:
        await _s().execute(
            sa.insert(roles).prefix_with("IGNORE").values(code=code, name=code)
        )

    # Grant role → permission
    for role_code, perm_codes in ROLES.items():
        for pc in perm_codes:
            rid = (await _s().execute(
                sa.select(roles.c.id).where(roles.c.code == role_code)
            )).scalar()
            pid = (await _s().execute(
                sa.select(permissions.c.id).where(permissions.c.code == pc)
            )).scalar()
            if rid and pid:
                await _s().execute(
                    sa.insert(role_permissions).prefix_with("IGNORE").values(
                        role_id=rid, permission_id=pid,
                    )
                )

    # Create admin user
    await _s().execute(
        sa.insert(users).prefix_with("IGNORE").values(
            username="admin",
            password=password_hasher(admin_password),
            real_name="系统管理员",
        )
    )

    # Grant admin role
    admin_uid = (await _s().execute(
        sa.select(users.c.id).where(users.c.username == "admin")
    )).scalar()
    admin_rid = (await _s().execute(
        sa.select(roles.c.id).where(roles.c.code == "admin")
    )).scalar()
    if admin_uid and admin_rid:
        await _s().execute(
            sa.insert(user_roles).prefix_with("IGNORE").values(
                user_id=admin_uid, role_id=admin_rid,
            )
        )
