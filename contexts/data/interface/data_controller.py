from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.container import container
from contexts.shared.domain.identifiers import UserId
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.domain.data_query import FilterCriterion
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import parse_int
from contexts.shared.interface.rest_controller import rest_controller

def _parse_filters(request) -> list[FilterCriterion]:
    filters: list[FilterCriterion] = []
    for raw in request.args.getlist("filter"):
        parts = raw.split(":", 2)
        if len(parts) == 3:
            filters.append(FilterCriterion(
                field=parts[0], operator=parts[1], value=parts[2]))
    return filters

def _parse_int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValidationError(f"invalid integer: {value}") from None

@rest_controller("/api")
class DataController(BaseController):
    name = "data_ddd"

    def __init__(self, data_svc: DataApplicationService):
        super().__init__()
        self.svc = data_svc

    def setup(self):
        self.bp.add_route(self.query,   "/data/<template_id:str>",            methods=["GET"])
        self.bp.add_route(self.get_row, "/data/<template_id:str>/<row_id:int>", methods=["GET"])
        self.bp.add_route(self.delete,  "/data/<template_id:str>/<row_id:int>", methods=["DELETE"])

    @require_auth
    @require_permission("data:view")
    @openapi.tag("Data")
    @openapi.summary("Query parsed data")
    async def query(self, request, template_id: str):
        batch_id = _parse_int_or_none(request.args.get("batch_id"))
        permissions = set(request.ctx.permissions or set())
        if "admin:roles" not in permissions and "user:manage" not in permissions:
            if batch_id is None:
                raise ValidationError("batch_id is required for project-scoped data access")
            await container.get(ProjectAccessPolicy).require_batch(
                UserId(request.ctx.user_id), batch_id,
            )
        page = parse_int(request.args.get("page"), 1)
        size = parse_int(request.args.get("size"), 200)
        return self.json(await self.svc.query(template_id, batch_id=batch_id, page=page, size=size,
                                          filters=_parse_filters(request)))

    @require_auth
    @require_permission("data:view")
    @openapi.tag("Data")
    @openapi.summary("Get single data row")
    async def get_row(self, request, template_id: str, row_id: int):
        permissions = set(request.ctx.permissions or set())
        if "admin:roles" not in permissions and "user:manage" not in permissions:
            await container.get(ProjectAccessPolicy).require_data_row(
                UserId(request.ctx.user_id), template_id, row_id,
            )
        return self.json(await self.svc.get_by_id(template_id, row_id))

    @require_auth
    @require_permission("data:delete")
    @openapi.tag("Data")
    @openapi.summary("Delete data row")
    async def delete(self, request, template_id: str, row_id: int):
        permissions = set(request.ctx.permissions or set())
        if "admin:roles" not in permissions and "user:manage" not in permissions:
            await container.get(ProjectAccessPolicy).require_data_row(
                UserId(request.ctx.user_id), template_id, row_id, {"manager"},
            )
        await self.svc.delete_by_id(template_id, row_id)
        return self.json_ok()
