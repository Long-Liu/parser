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

    async def delete_for_batches(self, batch_ids: list[int]) -> None:
        if not batch_ids:
            return
        for model in TEMPLATE_DATA_MODELS.values():
            await model.filter(batch_id__in=batch_ids).delete()
        await UploadLog.filter(batch_id__in=batch_ids).delete()
        await UploadPreview.filter(batch_id__in=batch_ids).delete()
        await UploadBatch.filter(id__in=batch_ids).delete()

    async def delete_for_project(self, project_id: int) -> None:
        batch_ids = list(await UploadBatch.filter(
            project_id=project_id
        ).values_list("id", flat=True))
        await self.delete_for_batches(batch_ids)
