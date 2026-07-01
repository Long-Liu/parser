# ponytail: migrated from api/batch_api.py + services/batch_service.py.
# Batch = ParseJob — query through ParseJobRepositoryImpl.

from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.parsing.infrastructure.repositories import ParseJobRepositoryImpl
from contexts.shared.domain.identifiers import ProjectId, JobId
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("batches", url_prefix="/api/batches")


def _job_to_dict(job) -> dict:
    return {
        "id": job.id.value,
        "project_id": job.project_id.value,
        "ym": str(job.year_month),
        "file_name": job.file_info.filename,
        "file_size": job.file_info.size,
        "status": job.status.value,
        "sheets": [
            {
                "sheet_name": s.sheet_name,
                "template_id": str(s.template_id) if s.template_id else None,
                "match_status": s.match_status.value,
                "total_rows": s.total_rows,
                "success_rows": s.success_rows,
                "error_rows": s.error_rows,
            }
            for s in job.sheets
        ],
    }


@bp.get("/")
@require_auth
@require_permission("data:view")
@openapi.tag("Batches")
@openapi.summary("List upload batches")
async def get_batches(request):
    repo = ParseJobRepositoryImpl()
    try:
        project_id_raw = request.args.get("project_id")
        if project_id_raw:
            jobs = await repo.find_by_project(ProjectId(int(project_id_raw)))
        else:
            jobs = await repo.find_by_project(ProjectId(0), limit=100)
        return json({"batches": [_job_to_dict(j) for j in jobs]})
    except DomainError as e:
        return error_to_response(e)


@bp.get("/<batch_id:int>")
@require_auth
@openapi.tag("Batches")
@openapi.summary("Get batch detail with sheet results")
async def get_batch_detail(request, batch_id: int):
    repo = ParseJobRepositoryImpl()
    try:
        job = await repo.find_by_id(JobId(batch_id))
        if job is None:
            return json({"error": "not found"}, status=404)
        return json(_job_to_dict(job))
    except DomainError as e:
        return error_to_response(e)
