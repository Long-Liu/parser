from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission, require_batch_access
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.parsing.application.batch_query_service import BatchQueryApplicationService
from contexts.shared.domain.identifiers import JobId, ProjectId, UserId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from, parse_int


class BatchesController(BaseController):
    name = "batches"
    url_prefix = "/api/batches"

    def __init__(self, batch_query_svc: BatchQueryApplicationService,
                 access_policy: ProjectAccessPolicy):
        super().__init__()
        self.batch_query_svc = batch_query_svc
        self.access_policy = access_policy

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
        project_id = None
        if project_id_raw:
            permissions = set(request.ctx.permissions or set())
            if not ProjectAccessPolicy.has_elevated_permission(permissions):
                await self.access_policy.require(
                    UserId(request.ctx.user_id), int(project_id_raw)
                )
            project_id = ProjectId(parse_int(project_id_raw, 0))
        result = await self.batch_query_svc.list_batches(project_id, pagination)
        if result is None:
            return self.json({"error": "project not found"}, status=404)
        return self.json(result)

    @require_auth
    @require_permission("data:view")
    @require_batch_access()
    @openapi.tag("Batches")
    @openapi.summary("Get batch detail with sheet results")
    async def get_batch(self, request, batch_id: int):
        result = await self.batch_query_svc.get_batch(JobId(batch_id))
        if result is None:
            return self.json({"error": "not found"}, status=404)
        return self.json(result)
