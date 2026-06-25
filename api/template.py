import re
from sanic import Blueprint
from sanic.response import json
from middleware.auth import require_auth, require_permission
from repositories.template import get_active_templates, register_template
from utils.config_loader import load_config
from db.schema import create_data_table

bp = Blueprint("templates", url_prefix="/api/templates")

_TEMPLATE_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")


@bp.get("/")
@require_auth
async def get_templates(request):
    pool = request.app.ctx.pool
    templates = await get_active_templates(pool)
    return json({"templates": templates})


@bp.post("/")
@require_auth
@require_permission("template:manage")
async def post_template(request):
    data = request.json
    template_id = data["template_id"]

    if not _TEMPLATE_ID_RE.match(template_id):
        return json({"error": "invalid template_id"}, status=400)

    config_yaml = data["config_yaml"]
    description = data.get("description", "")
    data_table = f"data_{template_id}"

    pool = request.app.ctx.pool
    tid = await register_template(pool, template_id, description, config_yaml, data_table)

    config = load_config(template_id)
    engine = request.app.ctx.engine
    await create_data_table(engine, template_id, config.get("columns", []))

    return json({"id": tid, "table": data_table}, status=201)
