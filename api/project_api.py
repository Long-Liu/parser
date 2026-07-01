from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from middleware.auth import require_auth, require_permission
from services.errors_service import ServiceError
from services.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from utils.validators import get_query_int, require_json_field

bp = Blueprint("projects", url_prefix="/api/projects")


@bp.get("/")
@require_auth
@require_permission("project:view")
@openapi.tag("Projects")
@openapi.summary("List projects")
async def get_projects(request):
    try:
        page = get_query_int(request.args, "page", 1)
        size = get_query_int(request.args, "size", 20)
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    if page < 1 or size < 1 or size > 1000:
        return json({"error": "page >= 1, 1 <= size <= 1000"}, status=400)

    result = await list_projects(page=page, size=size)
    return json(result)


@bp.get("/<project_id:int>")
@require_auth
@require_permission("project:view")
@openapi.tag("Projects")
@openapi.summary("Get project detail")
async def get_project_detail(request, project_id):
    project = await get_project(project_id)
    if not project:
        return json({"error": "not found"}, status=404)
    return json(project)


@bp.post("/")
@require_auth
@require_permission("project:create")
@openapi.tag("Projects")
@openapi.summary("Create project")
async def post_project(request):
    try:
        code = require_json_field(request.json, "code")
        name = require_json_field(request.json, "name")
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    try:
        result = await create_project(code=code, name=name, user_id=request.ctx.user_id)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json(result, status=201)


@bp.put("/<project_id:int>")
@require_auth
@require_permission("project:create")
@openapi.tag("Projects")
@openapi.summary("Update project")
async def put_project(request, project_id):
    data = request.json
    if data is None:
        return json({"error": "request body must be JSON"}, status=400)

    try:
        code = require_json_field(data, "code") if "code" in data else None
        name = require_json_field(data, "name") if "name" in data else None
        result = await update_project(project_id, code=code, name=name)
    except ValueError as e:
        return json({"error": str(e)}, status=400)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)

    return json(result)


@bp.delete("/<project_id:int>")
@require_auth
@require_permission("project:create")
@openapi.tag("Projects")
@openapi.summary("Delete project")
async def remove_project(request, project_id):
    try:
        await delete_project(project_id)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json({"deleted": True})
