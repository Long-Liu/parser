from __future__ import annotations

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.models import UploadBatch as OrmBatch
from db.models import UploadLog as OrmLog
from db.models import TEMPLATE_DATA_MODELS
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.parsing.domain.parse_job import (
    ParseJob, SheetResult, FileInfo, ParsedRow, MatchStatus, JobStatus,
)
from contexts.parsing.domain.repositories import ParseJobRepository


def _job_to_batch_values(job: ParseJob) -> dict:
    return {
        "project_id": job.project_id.value,
        "ym": str(job.year_month),
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
    job = ParseJob.submit(
        job_id=JobId(orm_batch.id),
        project_id=ProjectId(orm_batch.project_id),
        year_month=YearMonth.parse(orm_batch.ym),
        file_info=FileInfo(
            filename=orm_batch.file_name or "",
            size=orm_batch.file_size or 0,
        ),
    )
    for log in orm_logs:
        tid = TemplateId(log.template_id) if log.template_id else None
        ms = MatchStatus.SKIPPED
        if log.action == "matched":
            ms = MatchStatus.MATCHED
        sr = SheetResult(log.sheet_name, template_id=tid, match_status=ms)
        sr.total_rows = log.total_rows or 0
        sr.success_rows = log.success_rows or 0
        sr.error_rows = log.error_rows or 0
        job._sheets[log.sheet_name] = sr  # ponytail: direct dict access for reconstruction

    if orm_batch.status == "success":
        job.status = JobStatus.DONE
    elif orm_batch.status == "failed":
        job.status = JobStatus.FAILED
    return job


class ParseJobRepositoryImpl(ParseJobRepository):
    async def next_id(self) -> JobId:
        return JobId(0)

    async def save(self, job: ParseJob) -> None:
        batch_values = _job_to_batch_values(job)

        async def _save(session):
            if job.id.value > 0:
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
                # Insert new
                result = await session.execute(
                    sa.insert(OrmBatch.__table__).values(**batch_values)
                )
                job.id = JobId(result.lastrowid)

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

    async def insert_data_rows(
        self, template_id: str, rows: list[ParsedRow]
    ) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return
        data = []
        for row in rows:
            d = dict(row.fields)
            if row.hierarchy_code:
                d["hierarchy_code"] = row.hierarchy_code
            if row.monthly_data:
                d["monthly_data"] = row.monthly_data
            data.append(d)
        if not data:
            return

        async def _insert(session):
            session.add_all([model()(**row) for row in data])
            await session.flush()

        session = current_session()
        if session is not None:
            await _insert(session)
        else:
            async with get_sessionmaker().begin() as s:
                await _insert(s)
