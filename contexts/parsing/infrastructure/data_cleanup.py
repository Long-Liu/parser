"""Deletion of parsed upload data owned by the parsing context.

All 15 template data tables plus UploadPreview/UploadLog/UploadBatch rows are
keyed by ``batch_id``; this adapter is the single place that knows how to
remove them. Other contexts (project teardown, analytics monthly-data delete)
delegate here instead of duplicating the table list.
"""

from __future__ import annotations

from contexts.parsing.infrastructure.tables import (
    UploadBatch,
    UploadLog,
    UploadPreview,
)
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS


class ParsedDataCleanup:
    """Removes parsed data rows for upload batches."""

    # Chunk size for batch-keyed DELETEs: a huge single DELETE (thousands of
    # batch ids) can exhaust temp space / hold a wide lock range in one
    # statement. Chunking keeps each statement small; note that row locks are
    # still held until the caller's transaction commits — the gain is bounded
    # per-statement execution, not early lock release.
    _DELETE_BATCH_SIZE = 500

    @staticmethod
    async def delete_for_batches(batch_ids: list[int]) -> None:
        if not batch_ids:
            return
        for offset in range(0, len(batch_ids), ParsedDataCleanup._DELETE_BATCH_SIZE):
            chunk = batch_ids[offset : offset + ParsedDataCleanup._DELETE_BATCH_SIZE]
            for model in TEMPLATE_DATA_MODELS.values():
                await model.filter(batch_id__in=chunk).delete()
            await UploadLog.filter(batch_id__in=chunk).delete()
            await UploadPreview.filter(batch_id__in=chunk).delete()
            await UploadBatch.filter(id__in=chunk).delete()

    async def delete_for_project(self, project_id: int) -> None:
        batch_ids = list(
            await UploadBatch.filter(project_id=project_id).values_list(
                "id",
                flat=True,
            )
        )
        await self.delete_for_batches(batch_ids)
