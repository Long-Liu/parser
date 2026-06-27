"""Batch service."""

import sqlalchemy as sa

from db.tables import upload_batches
from repositories.batch import BatchRepo, LogRepo


async def list_batches(project_id: int | None = None, ym: str | None = None) -> list[dict]:
    if project_id is not None or ym:
        conditions = []
        if project_id is not None:
            conditions.append(upload_batches.c.project_id == project_id)
        if ym:
            conditions.append(upload_batches.c.ym == ym)
        return await BatchRepo.list(sa.and_(*conditions), order_by=upload_batches.c.id.desc())
    return await BatchRepo.list(order_by=upload_batches.c.id.desc())


async def get_batch(batch_id: int) -> dict | None:
    batch = await BatchRepo.get(BatchRepo.table.c.id == batch_id)
    if batch:
        batch["logs"] = await LogRepo.list(
            LogRepo.table.c.batch_id == batch_id, order_by=LogRepo.table.c.id
        )
    return batch
