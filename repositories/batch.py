import sqlalchemy as sa
from db.connection import execute, with_retry
from db.tables import upload_batches, upload_logs


@with_retry
async def create_batch(batch_no: str, project_id: int, ym: str,
                       uploaded_by: int, file_name: str, file_size: int) -> int:
    result = await execute(upload_batches.insert().values(
        batch_no=batch_no, project_id=project_id, ym=ym,
        uploaded_by=uploaded_by, file_name=file_name, file_size=file_size,
    ))
    return result.lastrowid


async def update_batch_status(batch_id: int, status: str):
    await execute(upload_batches.update()
                  .where(upload_batches.c.id == batch_id)
                  .values(status=status))


async def get_batch(batch_id: int) -> dict | None:
    result = await execute(upload_batches.select().where(upload_batches.c.id == batch_id))
    row = await result.fetchone()
    return dict(row) if row else None


async def list_batches(project_id: int = None, ym: str = None) -> list[dict]:
    conditions = []
    if project_id:
        conditions.append(upload_batches.c.project_id == project_id)
    if ym:
        conditions.append(upload_batches.c.ym == ym)
    stmt = upload_batches.select().order_by(upload_batches.c.id.desc())
    if conditions:
        stmt = stmt.where(sa.and_(*conditions))
    result = await execute(stmt)
    return [dict(r) for r in await result.fetchall()]


@with_retry
async def insert_log(batch_id: int, sheet_name: str, template_id: str,
                     action: str, total_rows: int = 0, success_rows: int = 0,
                     error_rows: int = 0, error_msg: str = None) -> int:
    result = await execute(upload_logs.insert().values(
        batch_id=batch_id, sheet_name=sheet_name,
        template_id=template_id, action=action,
        total_rows=total_rows, success_rows=success_rows,
        error_rows=error_rows, error_msg=error_msg,
    ))
    return result.lastrowid


async def get_logs_by_batch(batch_id: int) -> list[dict]:
    result = await execute(upload_logs.select()
                           .where(upload_logs.c.batch_id == batch_id)
                           .order_by(upload_logs.c.id))
    return [dict(r) for r in await result.fetchall()]
