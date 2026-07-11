from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission, require_batch_access
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.container import container
from contexts.shared.domain.identifiers import UserId
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.project.domain.repositories import ProjectRepository
from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from, parse_int
from contexts.shared.interface.rest_controller import rest_controller


def _job_to_dict(job) -> dict:
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

@rest_controller("/api")
class BatchesController(BaseController):
    name = "batches"
    url_prefix = "/api/batches"

    def __init__(self, parse_job_repo: ParseJobRepository,
                 project_repo: ProjectRepository):
        super().__init__()
        self.parse_job_repo = parse_job_repo
        self.project_repo = project_repo

    def setup(self):
        self.bp.add_route(self.list_batches, "/",               methods=["GET"])
        self.bp.add_route(self.get_batch,    "/<batch_id:int>", methods=["GET"])

    @require_auth
    @require_permission("data:view")
    @openapi.tag("Batches")
    @openapi.summary("List upload batches")
    async def list_batches(self, request):
        project_id_raw = request.args.get("project_id")
        pagination = pagination_from(request)
        if project_id_raw:
            permissions = set(request.ctx.permissions or set())
            if "admin:roles" not in permissions and "user:manage" not in permissions:
                await container.get(ProjectAccessPolicy).require(
                    UserId(request.ctx.user_id), int(project_id_raw)
                )
            project_id = ProjectId(parse_int(project_id_raw, 0))
            if await self.project_repo.find_by_id(project_id) is None:
                return self.json({"error": "project not found"}, status=404)
            jobs = await self.parse_job_repo.find_by_project(
                project_id, limit=pagination.size, offset=pagination.offset)
            total = await self.parse_job_repo.count(project_id)
        else:
            jobs = await self.parse_job_repo.list_recent(
                limit=pagination.size, offset=pagination.offset)
            total = await self.parse_job_repo.count()
        return self.json({
            "batches": [_job_to_dict(j) for j in jobs],
            "pagination": {"page": pagination.page,
                           "size": pagination.size, "total": total},
        })

    @require_auth
    @require_permission("data:view")
    @require_batch_access()
    @openapi.tag("Batches")
    @openapi.summary("Get batch detail with sheet results")
    async def get_batch(self, request, batch_id: int):
        job = await self.parse_job_repo.find_by_id(JobId(batch_id))
        if job is None:
            return self.json({"error": "not found"}, status=404)
        return self.json(_job_to_dict(job))
