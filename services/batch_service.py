"""Batch service."""

from repositories.batch_repository import BatchRepo, LogRepo


async def list_batches(project_id: int | None = None, ym: str | None = None) -> list[dict]:
    return await BatchRepo.list_filtered(project_id=project_id, ym=ym)


async def get_batch(batch_id: int) -> dict | None:
    batch = await BatchRepo.get_by_id(batch_id)
    if batch:
        batch["logs"] = await LogRepo.list_by_batch(batch_id)
    return batch
