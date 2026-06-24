async def create_project(pool, code: str, name: str, created_by: int = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO projects (code, name, created_by) VALUES (%s,%s,%s)",
                (code, name, created_by),
            )
            return cur.lastrowid


async def list_projects(pool) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM projects ORDER BY id DESC")
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
