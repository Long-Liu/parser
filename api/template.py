from sqlalchemy import text
from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth, require_permission
from parser.models.template import get_active_templates, register_template
from parser.utils.config_loader import load_config
from parser.db.schema import create_data_table

bp = Blueprint("templates", url_prefix="/api/templates")


@bp.get("/")
@require_auth
async def get_templates(request):
    session = request.app.ctx.Session()
    try:
        templates = await get_active_templates(session)
        return json({"templates": [{"template_id": t.template_id, "description": t.description, "data_table": t.data_table} for t in templates]})
    finally:
        await session.close()


@bp.post("/")
@require_auth
@require_permission("template:manage")
async def post_template(request):
    data = request.json
    session = request.app.ctx.Session()
    try:
        template_id = data["template_id"]
        config_yaml = data["config_yaml"]
        description = data.get("description", "")
        data_table = f"data_{template_id}"

        async with session.begin():
            tid = await register_template(session, template_id, description, config_yaml, data_table)
        config = load_config(template_id)
        await create_data_table(template_id, config.get("columns", []))
        return json({"id": tid, "table": data_table}, status=201)
    finally:
        await session.close()
