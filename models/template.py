async def register_template(pool, template_id: str, description: str,
                            config_yaml: str, data_table: str) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO template_configs (template_id, description, config_yaml, data_table) "
                "VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE config_yaml=VALUES(config_yaml), data_table=VALUES(data_table), "
                "description=VALUES(description)",
                (template_id, description, config_yaml, data_table),
            )
            return cur.lastrowid


async def get_template_by_id(pool, template_id: str) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM template_configs WHERE template_id=%s AND is_active=1",
                (template_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


async def get_active_templates(pool) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM template_configs WHERE is_active=1")
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
