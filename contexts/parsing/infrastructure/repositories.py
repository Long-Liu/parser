from __future__ import annotations

from datetime import datetime, timedelta, timezone

from contexts.parsing.domain.parse_job import (
    FileInfo,
    JobStatus,
    MatchStatus,
    ParseJob,
    SheetResult,
)
from contexts.parsing.domain.repositories import (
    ParseJobRepository,
    UploadPreviewRepository,
)
from contexts.parsing.infrastructure.tables import UploadBatch as OrmBatch
from contexts.parsing.infrastructure.tables import UploadLog as OrmLog
from contexts.parsing.infrastructure.tables import UploadPreview
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.infrastructure.database.queryset_helpers import fetch_values_list


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
    return {
        "batch_id": batch_id,
        "sheet_name": sheet.sheet_name,
        "template_id": str(sheet.template_id) if sheet.template_id else None,
        "action": (
            "matched"
            if sheet.match_status == MatchStatus.MATCHED
            else sheet.match_status.value
        ),
        "total_rows": sheet.total_rows,
        "success_rows": sheet.success_rows,
        "error_rows": sheet.error_rows,
    }


def _orm_to_job(orm_batch: OrmBatch, orm_logs: list[OrmLog]) -> ParseJob:
    sheets = []
    for log in orm_logs:
        tid = TemplateId(log.template_id) if log.template_id else None
        ms = MatchStatus.MATCHED if log.action == "matched" else MatchStatus.SKIPPED
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


class ParseJobRepositoryImpl(ParseJobRepository):
    async def save(self, job: ParseJob) -> None:
        batch_values = _job_to_batch_values(job)
        if job.id is None:
            batch = await OrmBatch.create(**batch_values)
            job.id = JobId(batch.id)
            return

        batch = await OrmBatch.get_or_none(id=job.id.value)
        if batch is None:
            batch = OrmBatch(id=job.id.value, **batch_values)
            await batch.save(force_create=True)
        else:
            for key, value in batch_values.items():
                setattr(batch, key, value)
            await batch.save(update_fields=list(batch_values.keys()))
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

    async def find_by_project(
        self, project_id: ProjectId, limit: int = 20, offset: int = 0
    ) -> list[ParseJob]:
        batches = await OrmBatch.filter(project_id=project_id.value).order_by(
            "-id"
        ).limit(limit).offset(offset)
        jobs = []
        for batch in batches:
            logs = await OrmLog.filter(batch_id=batch.id)
            jobs.append(_orm_to_job(batch, list(logs)))
        return jobs

    async def list_recent(self, limit: int = 100, offset: int = 0) -> list[ParseJob]:
        batches = await OrmBatch.all().order_by("-id").limit(limit).offset(offset)
        jobs = []
        for batch in batches:
            logs = await OrmLog.filter(batch_id=batch.id)
            jobs.append(_orm_to_job(batch, list(logs)))
        return jobs

    async def count(self, project_id: ProjectId | None = None) -> int:
        query = OrmBatch.all()
        if project_id is not None:
            query = query.filter(project_id=project_id.value)
        return await query.count()

class UploadPreviewRepositoryImpl(UploadPreviewRepository):
    async def save(self, batch_id: int, payload: list[dict], summary: list[dict]) -> None:
        from tortoise.exceptions import IntegrityError
        existing = await UploadPreview.get_or_none(batch_id=batch_id)
        if existing:
            existing.payload = payload
            existing.summary = summary
            existing.status = "pending"
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
                    existing.status = "pending"
                    await existing.save(update_fields=["payload", "summary", "status"])
                else:
                    raise

    async def get(self, batch_id: int) -> dict | None:
        row = await UploadPreview.get_or_none(batch_id=batch_id, status="pending")
        return None if row is None else {"payload": row.payload, "summary": row.summary}

    async def delete(self, batch_id: int) -> None:
        await UploadPreview.filter(batch_id=batch_id).delete()

    async def cleanup_expired(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        expired_ids = list(await fetch_values_list(UploadPreview.filter(
            status="pending", created_at__lt=cutoff,
        ), "batch_id", flat=True))
        if not expired_ids:
            return 0
        await UploadPreview.filter(batch_id__in=expired_ids).delete()
        await OrmBatch.filter(id__in=expired_ids, status="preview").update(
            status="cancelled"
        )
        return len(expired_ids)
