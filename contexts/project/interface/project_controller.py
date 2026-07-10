from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.shared.domain.identifiers import UserId
from contexts.shared.domain.exceptions import DomainError
from contexts.container import container
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("project_ddd", url_prefix="/api")


@bp.get("/projects")
@require_auth
@require_permission("project:view")
@openapi.tag("Project")
@openapi.summary("List projects")
async def list_projects(request):
    svc = container.get(ProjectApplicationService)
    result = await svc.list_all()
    return json(result)


@bp.post("/projects")
@require_auth
@require_permission("project:create")
@openapi.tag("Project")
@openapi.summary("Create project")
async def create_project(request):
    data = request.json or {}
    svc = container.get(ProjectApplicationService)
    try:
        raw_user_id = getattr(request.ctx, "user_id", None)
        created_by = UserId(raw_user_id) if raw_user_id else None
        result = await svc.create(
            code=data.get("code", ""),
            name=data.get("name", ""),
            created_by=created_by,
        )
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)


@bp.post("/projects/<project_id:int>/users/<user_id:int>")
@require_auth
@require_permission("user:manage")
@openapi.tag("Project")
@openapi.summary("Assign a user to a project")
async def assign_project_user(request, project_id: int, user_id: int):
    data = request.json or {}
    svc = container.get(ProjectApplicationService)
    try:
        await svc.assign_user(project_id, user_id, bool(data.get("is_primary", False)))
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)


@bp.delete("/projects/<project_id:int>/users/<user_id:int>")
@require_auth
@require_permission("user:manage")
@openapi.tag("Project")
@openapi.summary("Remove a user from a project")
async def remove_project_user(request, project_id: int, user_id: int):
    svc = container.get(ProjectApplicationService)
    try:
        await svc.remove_user(project_id, user_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)
