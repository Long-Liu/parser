from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from middleware.auth import require_auth, require_permission
from services.project import list_projects, create_project
from utils.validators import require_json_field

bp = Blueprint("projects", url_prefix="/api/projects")


@bp.get("/")
@require_auth
@require_permission("project:view")
@openapi.tag("Projects")
@openapi.summary("List projects")
async def get_projects(request):
    projects = await list_projects()
    return json({"projects": projects})


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

    result = await create_project(code=code, name=name, user_id=request.ctx.user_id)
    return json(result, status=201)
