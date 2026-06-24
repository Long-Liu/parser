from sqlalchemy import text
from middleware.auth import hash_password

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


async def seed_defaults(session):
    async with session.bind.begin() as conn:
        for code, name in PERMISSIONS:
            await conn.execute(text("INSERT IGNORE INTO permissions (code, name) VALUES (:c, :n)"), {"c": code, "n": name})
        for code in ROLES:
            await conn.execute(text("INSERT IGNORE INTO roles (code, name) VALUES (:c, :c)"), {"c": code})
        for role_code, perm_codes in ROLES.items():
            for pc in perm_codes:
                await conn.execute(
                    text("INSERT IGNORE INTO role_permissions (role_id, permission_id) "
                         "SELECT r.id, p.id FROM roles r, permissions p WHERE r.code=:rc AND p.code=:pc"),
                    {"rc": role_code, "pc": pc},
                )
        await conn.execute(
            text("INSERT IGNORE INTO users (username, password, real_name) VALUES (:u, :p, :n)"),
            {"u": "admin", "p": hash_password("admin123"), "n": "系统管理员"},
        )
        await conn.execute(
            text("INSERT IGNORE INTO user_roles (user_id, role_id) "
                 "SELECT u.id, r.id FROM users u, roles r WHERE u.username='admin' AND r.code='admin'"),
        )
