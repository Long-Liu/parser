from sanic import Blueprint
from sanic.response import json

from db.connection import execute
from db.schema import create_data_table
from middleware.auth import require_auth, require_permission
from repositories.template import get_active_templates, register_template
from utils.config_loader import load_config
from utils.validators import is_valid_template_id

bp = Blueprint("templates", url_prefix="/api/templates")


@bp.get("/")
@require_auth
async def get_templates(request):
    templates = await get_active_templates()
    return json({"templates": templates})


@bp.post("/")
@require_auth
@require_permission("template:manage")
async def post_template(request):
    data = request.json
    template_id = data["template_id"]

    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    config_yaml = data["config_yaml"]
    description = data.get("description", "")
    data_table = f"data_{template_id}"

    tid = await register_template(template_id, description, config_yaml, data_table)

    config = load_config(template_id)
    await create_data_table(template_id, config.get("columns", []))

    return json({"id": tid, "table": data_table}, status=201)
