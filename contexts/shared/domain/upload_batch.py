"""Upload batch status value type (shared kernel).

The parsing context owns upload batches, but the analytics/project/alert
contexts read batches and filter by status, so the status enum is shared
rather than forcing those contexts to depend on the parsing domain aggregate.
"""

from __future__ import annotations

from enum import StrEnum


class UploadBatchStatus(StrEnum):
    """Persisted status of an upload batch row (upload_batches.status) and the
    batch/sheet status surfaced by upload & preview APIs. Values are DB/API
    strings — do not rename."""

    PROCESSING = "processing"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    # Transient API-only status: returned by the preview endpoint, never
    # persisted on a batch row (batch rows carry result_status values only).
    PREVIEW = "preview"
