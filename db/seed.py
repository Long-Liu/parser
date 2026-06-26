"""Seed default permissions, roles, and admin user on first startup."""

import logging
import os

import sqlalchemy as sa

from db.connection import execute, Transaction
from db.tables import permissions, roles, users
from middleware.auth import hash_password

logger = logging.getLogger("parser.seed")

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


def _get_default_admin_password() -> str:
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    if not password:
        logger.warning(
            "DEFAULT_ADMIN_PASSWORD not set, using insecure default; change immediately"
        )
        password = "admin123"
    return password


async def seed_defaults():
    admin_password = _get_default_admin_password()

    async with Transaction() as conn:
        for code, name in PERMISSIONS:
            await conn.execute(
                permissions.insert().prefix_with("IGNORE").values(code=code, name=name)
            )
        for code in ROLES:
            await conn.execute(
                roles.insert().prefix_with("IGNORE").values(code=code, name=code)
            )
        for role_code, perm_codes in ROLES.items():
            for pc in perm_codes:
                await conn.execute(
                    sa.text(
                        "INSERT IGNORE INTO role_permissions (role_id, permission_id) "
                        "SELECT r.id, p.id FROM roles r, permissions p "
                        "WHERE r.code=:rc AND p.code=:pc"
                    ),
                    {"rc": role_code, "pc": pc},
                )
        await conn.execute(
            users.insert().prefix_with("IGNORE").values(
                username="admin", password=hash_password(admin_password),
                real_name="系统管理员",
            )
        )
        await conn.execute(
            sa.text(
                "INSERT IGNORE INTO user_roles (user_id, role_id) "
                "SELECT u.id, r.id FROM users u, roles r "
                "WHERE u.username=:un AND r.code=:rc"
            ),
            {"un": "admin", "rc": "admin"},
        )
