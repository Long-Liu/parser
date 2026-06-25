async def create_user(pool, username: str, password: str, real_name: str = None,
                      email: str = None, phone: str = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO users (username, password, real_name, email, phone) VALUES (%s,%s,%s,%s,%s)",
                (username, password, real_name, email, phone),
            )
            return cur.lastrowid


async def get_user_by_username(pool, username: str) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


async def get_user_by_id(pool, user_id: int) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
