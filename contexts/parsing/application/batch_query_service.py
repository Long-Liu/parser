"""Read-side application service for upload batch queries.

Controllers use this service instead of touching the parse-job and project
repositories directly; pagination orchestration and DTO mapping live here.
"""

from __future__ import annotations

from contexts.parsing.domain.parse_job import ParseJob
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.project.domain.repositories import ProjectRepository
from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.shared.domain.pagination import Pagination


def _job_to_dict(job: ParseJob) -> dict:
    return {
        "id":            job.id.value,
        "project_id":    job.project_id.value,
        "ym":            str(job.year_month),
        "file_name":     job.file_info.filename,
        "file_size":     job.file_info.size,
        "status":        job.result_status,
        "job_status":    job.status.value,
        "sheets": [
            {"sheet_name": s.sheet_name,
             "template_id": str(s.template_id) if s.template_id else None,
             "match_status": s.match_status.value,
             "total_rows": s.total_rows, "success_rows": s.success_rows,
             "error_rows": s.error_rows}
            for s in job.sheets
        ],
    }


class BatchQueryApplicationService:
    """Paginated batch listing and batch detail queries."""

    def __init__(self, parse_jobs: ParseJobRepository,
                 projects: ProjectRepository) -> None:
        self._parse_jobs = parse_jobs
        self._projects = projects

    async def list_batches(self, project_id: ProjectId | None,
                           pagination: Pagination) -> dict | None:
        """List batches, optionally scoped to one project.

        Returns ``None`` when a project scope was requested but the project
        does not exist (the interface layer maps that to a 404).
        """
        if project_id is not None:
            if await self._projects.find_by_id(project_id) is None:
                return None
            jobs = await self._parse_jobs.find_by_project(
                project_id, limit=pagination.size, offset=pagination.offset)
            total = await self._parse_jobs.count(project_id)
        else:
            jobs = await self._parse_jobs.list_recent(
                limit=pagination.size, offset=pagination.offset)
            total = await self._parse_jobs.count()
        return {
            "batches": [_job_to_dict(j) for j in jobs],
            "pagination": {"page": pagination.page,
                           "size": pagination.size, "total": total},
        }

    async def get_batch(self, batch_id: JobId) -> dict | None:
        job = await self._parse_jobs.find_by_id(batch_id)
        return None if job is None else _job_to_dict(job)
