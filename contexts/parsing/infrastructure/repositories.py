from __future__ import annotations

import sqlalchemy as sa

from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.models import UploadBatch as OrmBatch
from contexts.shared.infrastructure.database.models import UploadLog as OrmLog
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.parsing.domain.parse_job import (
    ParseJob, SheetResult, FileInfo, ParsedRow, MatchStatus, JobStatus,
)
from contexts.parsing.domain.repositories import ParseJobRepository


def _job_to_batch_values(job: ParseJob) -> dict:
    return {
        "batch_no": job.batch_no,
        "project_id": job.project_id.value,
        "ym": str(job.year_month),
        "uploaded_by": job.uploaded_by.value if job.uploaded_by else None,
        "file_name": job.file_info.filename,
        "file_size": job.file_info.size,
        "status": job.overall_status,
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
        sr = SheetResult(log.sheet_name, template_id=tid, match_status=ms)
        sr.total_rows = log.total_rows or 0
        sr.success_rows = log.success_rows or 0
        sr.error_rows = log.error_rows or 0
        sheets.append(sr)

    status = JobStatus.FAILED if orm_batch.status == "failed" else JobStatus.DONE
    return ParseJob.rehydrate(
        job_id=JobId(orm_batch.id),
        project_id=ProjectId(orm_batch.project_id),
        year_month=YearMonth.parse(orm_batch.ym),
        file_info=FileInfo(
            filename=orm_batch.file_name or "",
            size=orm_batch.file_size or 0,
        ),
        batch_no=orm_batch.batch_no or "",
        uploaded_by=UserId(orm_batch.uploaded_by) if orm_batch.uploaded_by else None,
        status=status,
        sheets=sheets,
    )


class ParseJobRepositoryImpl(ParseJobRepository):
    async def save(self, job: ParseJob) -> None:
        batch_values = _job_to_batch_values(job)

        async def _save(session):
            if job.id is None:
                result = await session.execute(
                    sa.insert(OrmBatch.__table__).values(**batch_values)
                )
                job.id = JobId(result.lastrowid)
                return
            exists = await session.execute(
                sa.select(OrmBatch.__table__.c.id).where(
                    OrmBatch.__table__.c.id == job.id.value
                )
            )
            if exists.first() is not None:
                # Update existing
                await session.execute(
                    sa.update(OrmBatch.__table__)
                    .where(OrmBatch.__table__.c.id == job.id.value)
                    .values(**batch_values)
                )
                await session.execute(
                    sa.delete(OrmLog.__table__).where(
                        OrmLog.__table__.c.batch_id == job.id.value
                    )
                )
            else:
                await session.execute(
                    sa.insert(OrmBatch.__table__).values(
                        id=job.id.value, **batch_values
                    )
                )

            batch_id = job.id.value
            for sheet in job.sheets:
                log_vals = _sheet_to_log_values(sheet, batch_id)
                await session.execute(
                    sa.insert(OrmLog.__table__).values(**log_vals)
                )

        session = current_session()
        if session is not None:
            await _save(session)
        else:
            async with get_sessionmaker().begin() as s:
                await _save(s)

    async def find_by_id(self, job_id: JobId) -> ParseJob | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmBatch).where(OrmBatch.__table__.c.id == job_id.value)
            )
            batch = result.scalars().first()
            if batch is None:
                return None
            logs_result = await s.execute(
                sa.select(OrmLog).where(OrmLog.__table__.c.batch_id == job_id.value)
            )
            return _orm_to_job(batch, list(logs_result.scalars().all()))

        session = current_session()
        if session is not None:
            return await _find(session)
        async with get_sessionmaker()() as s:
            return await _find(s)

    async def find_by_project(
        self, project_id: ProjectId, limit: int = 20, offset: int = 0
    ) -> list[ParseJob]:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmBatch)
                .where(OrmBatch.__table__.c.project_id == project_id.value)
                .order_by(OrmBatch.__table__.c.id.desc())
                .limit(limit)
                .offset(offset)
            )
            jobs = []
            for batch in result.scalars().all():
                logs_result = await s.execute(
                    sa.select(OrmLog).where(
                        OrmLog.__table__.c.batch_id == batch.id
                    )
                )
                jobs.append(
                    _orm_to_job(batch, list(logs_result.scalars().all()))
                )
            return jobs

        session = current_session()
        if session is not None:
            return await _find(session)
        async with get_sessionmaker()() as s:
            return await _find(s)

    async def list_recent(self, limit: int = 100, offset: int = 0) -> list[ParseJob]:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmBatch)
                .order_by(OrmBatch.__table__.c.id.desc())
                .limit(limit)
                .offset(offset)
            )
            jobs = []
            for batch in result.scalars().all():
                logs_result = await s.execute(
                    sa.select(OrmLog).where(
                        OrmLog.__table__.c.batch_id == batch.id
                    )
                )
                jobs.append(
                    _orm_to_job(batch, list(logs_result.scalars().all()))
                )
            return jobs

        session = current_session()
        if session is not None:
            return await _find(session)
        async with get_sessionmaker()() as s:
            return await _find(s)
