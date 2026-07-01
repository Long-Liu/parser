"""Batch service."""

import sqlalchemy as sa

from repositories.batch import BatchRepo, LogRepo


async def list_batches(project_id: int | None = None, ym: str | None = None) -> list[dict]:
    if project_id is not None or ym:
        conditions = []
        if project_id is not None:
            conditions.append(BatchRepo._t().c.project_id == project_id)
        if ym:
            conditions.append(BatchRepo._t().c.ym == ym)
        return await BatchRepo.list(sa.and_(*conditions), order_by=BatchRepo._t().c.id.desc())
    return await BatchRepo.list(order_by=BatchRepo._t().c.id.desc())


async def get_batch(batch_id: int) -> dict | None:
    batch = await BatchRepo.get(BatchRepo._t().c.id == batch_id)
    if batch:
        batch["logs"] = await LogRepo.list(
            LogRepo._t().c.batch_id == batch_id, order_by=LogRepo._t().c.id
        )
    return batch
