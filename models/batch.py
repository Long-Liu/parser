from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from parser.db.models import UploadBatch, UploadLog


async def create_batch(session: AsyncSession, batch_no: str, project_id: int, ym: str,
                       uploaded_by: int, file_name: str, file_size: int) -> int:
    batch = UploadBatch(batch_no=batch_no, project_id=project_id, ym=ym,
                         uploaded_by=uploaded_by, file_name=file_name, file_size=file_size)
    session.add(batch)
    await session.flush()
    return batch.id


async def update_batch_status(session: AsyncSession, batch_id: int, status: str):
    batch = await session.get(UploadBatch, batch_id)
    if batch:
        batch.status = status


async def get_batch(session: AsyncSession, batch_id: int) -> UploadBatch | None:
    return await session.get(UploadBatch, batch_id)


async def list_batches(session: AsyncSession, project_id: int = None, ym: str = None) -> list[UploadBatch]:
    stmt = select(UploadBatch)
    if project_id:
        stmt = stmt.where(UploadBatch.project_id == project_id)
    if ym:
        stmt = stmt.where(UploadBatch.ym == ym)
    stmt = stmt.order_by(UploadBatch.id.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def insert_log(session: AsyncSession, batch_id: int, sheet_name: str, template_id: str,
                     action: str, total_rows: int = 0, success_rows: int = 0,
                     error_rows: int = 0, error_msg: str = None) -> int:
    log = UploadLog(batch_id=batch_id, sheet_name=sheet_name, template_id=template_id,
                     action=action, total_rows=total_rows, success_rows=success_rows,
                     error_rows=error_rows, error_msg=error_msg)
    session.add(log)
    await session.flush()
    return log.id


async def get_logs_by_batch(session: AsyncSession, batch_id: int) -> list[UploadLog]:
    result = await session.execute(
        select(UploadLog).where(UploadLog.batch_id == batch_id).order_by(UploadLog.id)
    )
    return result.scalars().all()
