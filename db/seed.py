from db.connection import transactional
from middleware.auth import hash_password
from repositories.user import (UserRepo, RoleRepo, PermissionRepo,
                                UserRoleRepo, RolePermissionRepo)


async def seed_defaults():
    """Seed default permissions, roles, and admin user on first startup."""
    import os
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

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

    await _do_seed(admin_password, PERMISSIONS, ROLES)


@transactional
async def _do_seed(admin_password: str, PERMISSIONS: list, ROLES: dict):
    for code, name in PERMISSIONS:
        await PermissionRepo.insert_ignore(code=code, name=name)
    for code in ROLES:
        await RoleRepo.insert_ignore(code=code, name=code)

    for role_code, perm_codes in ROLES.items():
        for pc in perm_codes:
            await RolePermissionRepo.grant(role_code, pc)
    await UserRepo.insert_ignore(
        username="admin", password=hash_password(admin_password),
        real_name="系统管理员",
    )
    await UserRoleRepo.grant_to_user("admin", "admin")
