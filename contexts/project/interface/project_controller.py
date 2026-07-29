from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from sanic_ext import openapi

from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.auth.interface.auth_middleware import (
    require_auth,
    require_permission,
    require_project_access,
)
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from


def _project_details(data: dict) -> dict:
    result: dict[str, object] = {}
    for key in ("project_type", "stage", "status", "description"):
        if key in data:
            result[key] = str(data[key] or "")
    for key in ("capacity_mw", "contract_price", "progress"):
        if key in data:
            try:
                result[key] = Decimal(str(data[key]))
            except InvalidOperation:
                raise ValidationError(f"invalid decimal: {key}") from None
    for key in ("start_date", "end_date"):
        if key in data:
            try:
                result[key] = date.fromisoformat(data[key]) if data[key] else None
            except (TypeError, ValueError):
                raise ValidationError(f"invalid date: {key}") from None
    if "manager_id" in data:
        result["manager_id"] = UserId(int(data["manager_id"])) if data["manager_id"] else None
    return result


def _ui_project_payload(data: dict) -> dict:
    """Accept both API names and the published project's form aliases."""
    result = dict(data)
    for source, target in {
        "contract": "contract_price",
        "startDate": "start_date",
        "endDate": "end_date",
        "notes": "description",
    }.items():
        if source in result and target not in result:
            result[target] = result[source]
    if "leader" in result and "manager_name" not in result:
        result["manager_name"] = result["leader"]
    return result


class ProjectsController(BaseController):
    name = "project"

    def __init__(self, project_svc: ProjectApplicationService):
        super().__init__()
        self.svc = project_svc

    def setup(self):
        self.bp.add_route(self.list_projects, "/projects", methods=["GET"])
        self.bp.add_route(self.create_project, "/projects", methods=["POST"])
        self.bp.add_route(self.get_project, "/projects/<project_id:int>", methods=["GET"])
        self.bp.add_route(self.update_project, "/projects/<project_id:int>", methods=["PUT"])
        self.bp.add_route(self.delete_project, "/projects/<project_id:int>", methods=["DELETE"])
        self.bp.add_route(self.assign_user, "/projects/<project_id:int>/users/<user_id:int>", methods=["POST"])
        self.bp.add_route(self.remove_user, "/projects/<project_id:int>/users/<user_id:int>", methods=["DELETE"])

    @require_auth
    @require_permission("project:view")
    @openapi.tag("Project")
    @openapi.summary("List projects")
    async def list_projects(self, request):
        permissions = set(request.ctx.permissions or set())
        scoped_user_id = None
        if not ProjectAccessPolicy.has_elevated_permission(permissions):
            scoped_user_id = UserId(request.ctx.user_id)
        result = await self.svc.list_all(
            keyword=request.args.get("keyword", ""),
            status=request.args.get("status", ""),
            pagination=pagination_from(request),
            user_id=scoped_user_id,
        )
        return self.json(result)

    @require_auth
    @require_permission("project:create")
    @openapi.tag("Project")
    @openapi.summary("Create project")
    async def create_project(self, request):
        data = _ui_project_payload(request.json or {})
        raw_user_id = getattr(request.ctx, "user_id", None)
        created_by = UserId(raw_user_id) if raw_user_id else None
        details = _project_details(data)
        if data.get("manager_name"):
            details["manager_name"] = str(data["manager_name"])
        result = await self.svc.create(
            code=data.get("code", ""),
            name=data.get("name", ""),
            created_by=created_by,
            **details,
        )
        return self.json(result, status=201)

    @require_auth
    @require_permission("project:view")
    @require_project_access()
    async def get_project(self, request, project_id: int):
        return self.json(await self.svc.get_by_id(ProjectId(project_id)))

    @require_auth
    @require_permission("project:create")
    @require_project_access(roles={"manager"})
    async def update_project(self, request, project_id: int):
        data = _ui_project_payload(request.json or {})
        details = _project_details(data)
        if "name" in data:
            details["name"] = data["name"]
        if data.get("manager_name"):
            details["manager_name"] = str(data["manager_name"])
        return self.json(await self.svc.update(project_id, **details))

    @require_auth
    @require_permission("project:create")
    @require_project_access(roles={"manager"})
    async def delete_project(self, request, project_id: int):
        await self.svc.delete(project_id)
        return self.json_ok()

    @require_auth
    @require_permission("user:manage")
    @openapi.tag("Project")
    @openapi.summary("Assign a user to a project")
    async def assign_user(self, request, project_id: int, user_id: int):
        data = request.json or {}
        await self.svc.assign_user(
            project_id,
            user_id,
            bool(data.get("is_primary", False)),
            data.get("role", "manager" if data.get("is_primary") else "viewer"),
        )
        return self.json_ok()

    @require_auth
    @require_permission("user:manage")
    @openapi.tag("Project")
    @openapi.summary("Remove a user from a project")
    async def remove_user(self, request, project_id: int, user_id: int):
        await self.svc.remove_user(project_id, user_id)
        return self.json_ok()
