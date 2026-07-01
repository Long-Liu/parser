from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.infrastructure.repositories import ProjectRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("project_ddd", url_prefix="/api")


@bp.get("/projects")
@require_auth
@openapi.tag("Project")
@openapi.summary("List projects")
async def list_projects(request):
    svc = ProjectApplicationService(ProjectRepositoryImpl())
    result = await svc.list_all()
    return json(result)


@bp.post("/projects")
@require_auth
@openapi.tag("Project")
@openapi.summary("Create project")
async def create_project(request):
    data = request.json or {}
    svc = ProjectApplicationService(ProjectRepositoryImpl())
    try:
        result = await svc.create(code=data.get("code", ""), name=data.get("name", ""),
                                  created_by=getattr(request.ctx, "user_id", None))
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)
