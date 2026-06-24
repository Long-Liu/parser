from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth, require_permission
from parser.models.project import create_project, list_projects

bp = Blueprint("projects", url_prefix="/api/projects")


@bp.get("/")
@require_auth
@require_permission("project:view")
async def get_projects(request):
    session = request.app.ctx.Session()
    try:
        projects = await list_projects(session)
        return json({"projects": [{"id": p.id, "code": p.code, "name": p.name} for p in projects]})
    finally:
        await session.close()


@bp.post("/")
@require_auth
@require_permission("project:create")
async def post_project(request):
    data = request.json
    session = request.app.ctx.Session()
    try:
        async with session.begin():
            pid = await create_project(session, data["code"], data["name"], request.ctx.user_id)
        return json({"id": pid, "code": data["code"]}, status=201)
    finally:
        await session.close()
