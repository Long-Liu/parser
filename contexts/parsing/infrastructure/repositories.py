from __future__ import annotations

from contexts.parsing.domain.parse_job import (
    FileInfo,
    JobStatus,
    MatchStatus,
    ParseJob,
    SheetResult,
)
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.parsing.infrastructure.tables import UploadBatch as OrmBatch
from contexts.parsing.infrastructure.tables import UploadLog as OrmLog
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId
from contexts.shared.domain.year_month import YearMonth


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

    status = JobStatus.FAILED if orm_batch.status == "failed" else JobStatus.DONE
    job = ParseJob(
        job_id=JobId(orm_batch.id),
        project_id=ProjectId(orm_batch.project_id),
        year_month=YearMonth.parse(orm_batch.ym),
        file_info=FileInfo(
            filename=orm_batch.file_name or "",
            size=orm_batch.file_size or 0,
        ),
        batch_no=orm_batch.batch_no or "",
        uploaded_by=UserId(orm_batch.uploaded_by) if orm_batch.uploaded_by else None,
    )
    job.status = status
    job._sheets = {s.sheet_name: s for s in sheets}  # type: ignore[attr-defined]
    return job


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
