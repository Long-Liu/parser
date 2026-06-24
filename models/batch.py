async def create_batch(pool, batch_no: str, project_id: int, ym: str,
                       uploaded_by: int, file_name: str, file_size: int) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO upload_batches (batch_no, project_id, ym, uploaded_by, file_name, file_size) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (batch_no, project_id, ym, uploaded_by, file_name, file_size),
            )
            return cur.lastrowid


async def update_batch_status(pool, batch_id: int, status: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE upload_batches SET status=%s WHERE id=%s", (status, batch_id)
            )


async def get_batch(pool, batch_id: int) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM upload_batches WHERE id=%s", (batch_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


async def list_batches(pool, project_id: int = None, ym: str = None) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            sql = "SELECT * FROM upload_batches WHERE 1=1"
            params = []
            if project_id:
                sql += " AND project_id=%s"
                params.append(project_id)
            if ym:
                sql += " AND ym=%s"
                params.append(ym)
            sql += " ORDER BY id DESC"
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]


async def insert_log(pool, batch_id: int, sheet_name: str, template_id: str,
                     action: str, total_rows: int = 0, success_rows: int = 0,
                     error_rows: int = 0, error_msg: str = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO upload_logs (batch_id, sheet_name, template_id, action, total_rows, success_rows, error_rows, error_msg) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (batch_id, sheet_name, template_id, action, total_rows, success_rows, error_rows, error_msg),
            )
            return cur.lastrowid


async def get_logs_by_batch(pool, batch_id: int) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM upload_logs WHERE batch_id=%s ORDER BY id",
                (batch_id,),
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
