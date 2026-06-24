async def seed_defaults(pool):
    permissions = [
        ("project:create", "创建项目"),
        ("project:view", "查看项目"),
        ("data:upload", "数据上传"),
        ("data:view", "数据查看"),
        ("data:export", "数据导出"),
        ("template:manage", "模板管理"),
        ("user:manage", "用户管理"),
    ]
    roles = [
        ("admin", "管理员"),
        ("manager", "项目经理"),
        ("viewer", "查看者"),
    ]
    role_perms = {
        "admin": ["project:create", "project:view", "data:upload", "data:view",
                   "data:export", "template:manage", "user:manage"],
        "manager": ["project:view", "data:upload", "data:view", "data:export"],
        "viewer": ["project:view", "data:view"],
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for code, name in permissions:
                await cur.execute(
                    "INSERT IGNORE INTO permissions (code, name) VALUES (%s, %s)",
                    (code, name),
                )
            for code, name in roles:
                await cur.execute(
                    "INSERT IGNORE INTO roles (code, name) VALUES (%s, %s)",
                    (code, name),
                )
            for role_code, perm_codes in role_perms.items():
                await cur.execute("SELECT id FROM roles WHERE code = %s", (role_code,))
                role_row = await cur.fetchone()
                if not role_row:
                    continue
                role_id = role_row[0]
                for pc in perm_codes:
                    await cur.execute(
                        "SELECT id FROM permissions WHERE code = %s", (pc,)
                    )
                    perm_row = await cur.fetchone()
                    if not perm_row:
                        continue
                    await cur.execute(
                        "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                        (role_id, perm_row[0]),
                    )

            # Create default admin user (password: admin123)
            from parser.middleware.auth import hash_password
            await cur.execute(
                "INSERT IGNORE INTO users (username, password, real_name) VALUES (%s, %s, %s)",
                ("admin", hash_password("admin123"), "系统管理员"),
            )
            await cur.execute("SELECT id FROM users WHERE username='admin'")
            user_row = await cur.fetchone()
            if user_row:
                await cur.execute("SELECT id FROM roles WHERE code='admin'")
                role_row = await cur.fetchone()
                if role_row:
                    await cur.execute(
                        "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)",
                        (user_row[0], role_row[0]),
                    )
