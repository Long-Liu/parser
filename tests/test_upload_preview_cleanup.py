"""Regression tests for expired-preview cleanup.

cleanup_expired previously filtered UploadBatch on status="preview", which can
never be written (result_status yields failed/skipped/success/partial), so
expired preview batches were never flipped to cancelled."""

from datetime import UTC, datetime, timedelta

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.parsing.infrastructure.repositories import TortoiseUploadPreviewRepository
from contexts.parsing.infrastructure.tables import UploadBatch, UploadPreview

# noinspection PyProtectedMember
from contexts.shared.infrastructure.database.engine import _MODEL_MODULES


@pytest.fixture
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": list(_MODEL_MODULES)},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


async def test_cleanup_expired_cancels_stale_batches(db):
    repo = TortoiseUploadPreviewRepository()
    await UploadBatch.create(
        id=1,
        batch_no="B-EXPIRED",
        project_id=1,
        ym="2026-07",
        status="success",
    )
    await UploadPreview.create(batch_id=1, payload=[], summary=[])

    # Backdate the preview beyond the expiry window.
    old = datetime.now(UTC) - timedelta(hours=2)
    await UploadPreview.filter(batch_id=1).update(created_at=old)

    deleted = await repo.cleanup_expired(max_age_hours=1)

    assert deleted == 1
    assert await UploadPreview.filter(batch_id=1).count() == 0
    batch = await UploadBatch.get(id=1)
    assert batch.status == "cancelled"


async def test_cleanup_expired_keeps_fresh_previews(db):
    repo = TortoiseUploadPreviewRepository()
    await UploadBatch.create(
        id=2,
        batch_no="B-FRESH",
        project_id=1,
        ym="2026-07",
        status="success",
    )
    await UploadPreview.create(batch_id=2, payload=[], summary=[])

    deleted = await repo.cleanup_expired(max_age_hours=1)

    assert deleted == 0
    assert await UploadPreview.filter(batch_id=2).count() == 1
    batch = await UploadBatch.get(id=2)
    assert batch.status == "success"
