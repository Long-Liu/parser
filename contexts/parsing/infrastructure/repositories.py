from __future__ import annotations

from datetime import UTC, datetime, timedelta

from contexts.parsing.domain.parse_job import (
    FileInfo,
    MatchStatus,
    ParseJob,
    PreviewStatus,
    SheetResult,
)
from contexts.shared.domain.upload_batch import UploadBatchStatus
from contexts.parsing.domain.repositories import (
    ParseJobRepository,
    UploadPreviewRepository,
)
from contexts.parsing.domain.year_month import YearMonth
from contexts.parsing.infrastructure.tables import UploadBatch as OrmBatch
from contexts.parsing.infrastructure.tables import UploadLog as OrmLog
from contexts.parsing.infrastructure.tables import UploadPreview
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId


def _job_to_batch_values(job: ParseJob) -> dict:
    return {
        "batch_no": job.batch_no,
        "project_id": job.project_id.value,
        "ym": str(job.year_month),
        "uploaded_by": job.uploaded_by.value if job.uploaded_by else None,
        "file_name": job.file_info.filename,
        "file_size": job.file_info.size,
        "status": job.result_status,
    }


def _sheet_to_log_values(sheet: SheetResult, batch_id: int) -> dict:
    tid = sheet.template_id
    template_id = None
    if tid is not None:
        template_id = tid.value
    return {
        "batch_id": batch_id,
        "sheet_name": sheet.sheet_name,
        "template_id": template_id,
        "action": sheet.match_status.value,
        "total_rows": sheet.total_rows,
        "success_rows": sheet.success_rows,
        "error_rows": sheet.error_rows,
    }


def _orm_to_job(orm_batch: OrmBatch, orm_logs: list[OrmLog]) -> ParseJob:
    sheets = []
    for log in orm_logs:
        tid = TemplateId(log.template_id) if log.template_id else None
        ms = MatchStatus.MATCHED if log.action == MatchStatus.MATCHED.value else MatchStatus.SKIPPED
        sr = SheetResult(
            sheet_name=log.sheet_name or "",
            template_id=tid,
            match_status=ms,
            total_rows=log.total_rows or 0,
            success_rows=log.success_rows or 0,
            error_rows=log.error_rows or 0,
        )
        sheets.append(sr)

    return ParseJob.reconstitute(
        job_id=JobId(orm_batch.id),
        project_id=ProjectId(orm_batch.project_id),
        year_month=YearMonth.parse(orm_batch.ym),
        file_info=FileInfo(
            filename=orm_batch.file_name or "",
            size=orm_batch.file_size or 0,
        ),
        status=orm_batch.status or "submitted",
        sheets=sheets,
        batch_no=orm_batch.batch_no or "",
        uploaded_by=UserId(orm_batch.uploaded_by) if orm_batch.uploaded_by else None,
    )


class TortoiseParseJobRepository(ParseJobRepository):
    async def save(self, job: ParseJob) -> None:
        batch_values = _job_to_batch_values(job)
        if job.id is None:
            batch = await OrmBatch.create(**batch_values)
            job.id = JobId(batch.id)
            return

        existing = await OrmBatch.get_or_none(id=job.id.value)
        if existing is None:
            created_batch = OrmBatch(id=job.id.value, **batch_values)
            await created_batch.save(force_create=True)
        else:
            for key, value in batch_values.items():
                setattr(existing, key, value)
            await existing.save(update_fields=list(batch_values.keys()))
            await OrmLog.filter(batch_id=job.id.value).delete()

        batch_id = job.id.value
        logs = [OrmLog(**_sheet_to_log_values(sheet, batch_id)) for sheet in job.sheets]
        if logs:
            await OrmLog.bulk_create(logs)

    async def find_by_id(self, job_id: JobId) -> ParseJob | None:
        batch = await OrmBatch.get_or_none(id=job_id.value)
        if batch is None:
            return None
        logs = await OrmLog.filter(batch_id=job_id.value)
        return _orm_to_job(batch, list(logs))

    async def find_by_project(self, project_id: ProjectId, limit: int = 20, offset: int = 0) -> list[ParseJob]:
        batches = await OrmBatch.filter(project_id=project_id.value).order_by("-id").limit(limit).offset(offset)
        return await self._jobs_with_logs(batches)

    async def list_recent(self, limit: int = 100, offset: int = 0) -> list[ParseJob]:
        batches = await OrmBatch.all().order_by("-id").limit(limit).offset(offset)
        return await self._jobs_with_logs(batches)

    async def find_by_projects(self, project_ids: list[ProjectId], limit: int = 20, offset: int = 0) -> list[ParseJob]:
        batches = (
            await OrmBatch.filter(project_id__in=[p.value for p in project_ids])
            .order_by("-id")
            .limit(limit)
            .offset(offset)
        )
        return await self._jobs_with_logs(batches)

    async def count_projects(self, project_ids: list[ProjectId]) -> int:
        return await OrmBatch.filter(project_id__in=[p.value for p in project_ids]).count()

    @staticmethod
    async def _jobs_with_logs(batches) -> list[ParseJob]:
        """Assemble jobs with a single batched log query (avoids N+1)."""
        if not batches:
            return []
        logs = await OrmLog.filter(batch_id__in=[batch.id for batch in batches])
        grouped: dict[int, list[OrmLog]] = {}
        for log in logs:
            grouped.setdefault(log.batch_id, []).append(log)
        return [_orm_to_job(batch, grouped.get(batch.id, [])) for batch in batches]

    async def count(self, project_id: ProjectId | None = None) -> int:
        query = OrmBatch.all()
        if project_id is not None:
            query = query.filter(project_id=project_id.value)
        return await query.count()


class TortoiseUploadPreviewRepository(UploadPreviewRepository):
    async def save(self, batch_id: int, payload: list[dict], summary: list[dict]) -> None:
        # noinspection PyPackageRequirements
        from tortoise.exceptions import IntegrityError

        pending = PreviewStatus.PENDING.value
        existing = await UploadPreview.get_or_none(batch_id=batch_id)
        if existing:
            existing.payload = payload
            existing.summary = summary
            existing.status = pending
            await existing.save(update_fields=["payload", "summary", "status"])
        else:
            try:
                await UploadPreview.create(batch_id=batch_id, payload=payload, summary=summary)
            except IntegrityError:
                # Race: another concurrent request created the record between
                # our get_or_none and create. Fall back to update.
                existing = await UploadPreview.get_or_none(batch_id=batch_id)
                if existing:
                    existing.payload = payload
                    existing.summary = summary
                    existing.status = pending
                    await existing.save(update_fields=["payload", "summary", "status"])
                else:
                    raise

    async def get(self, batch_id: int) -> dict | None:
        row = await UploadPreview.get_or_none(batch_id=batch_id, status=PreviewStatus.PENDING.value)
        return None if row is None else {"payload": row.payload, "summary": row.summary}

    async def delete(self, batch_id: int) -> None:
        await UploadPreview.filter(batch_id=batch_id).delete()

    async def cleanup_expired(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        expired_ids = list(
            await UploadPreview.filter(
                status=PreviewStatus.PENDING.value,
                created_at__lt=cutoff,
            ).values_list("batch_id", flat=True)
        )
        if not expired_ids:
            return 0
        await UploadPreview.filter(batch_id__in=expired_ids).delete()
        # Expired preview batches must be flipped to cancelled regardless of
        # their current status: batch rows never carry status "preview"
        # (result_status yields failed/skipped/success/partial), so filtering
        # on it here would silently leave stale success/partial rows behind.
        await OrmBatch.filter(id__in=expired_ids).update(status=UploadBatchStatus.CANCELLED)
        return len(expired_ids)
