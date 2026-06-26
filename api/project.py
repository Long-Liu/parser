from sanic import Blueprint
from sanic.response import json
from middleware.auth import require_auth, require_permission
from repositories.project import create_project, list_projects

bp = Blueprint("projects", url_prefix="/api/projects")


@bp.get("/")
@require_auth
@require_permission("project:view")
async def get_projects(request):
    projects = await list_projects()
    return json({"projects": projects})


@bp.post("/")
@require_auth
@require_permission("project:create")
async def post_project(request):
    data = request.json
    pid = await create_project(code=data["code"], name=data["name"], created_by=request.ctx.user_id)
    return json({"id": pid, "code": data["code"]}, status=201)
