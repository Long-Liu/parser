from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from middleware.auth import require_auth, require_permission
from services.template_service import list_templates, register_template
from utils.validators import is_valid_template_id, require_json_field

bp = Blueprint("templates", url_prefix="/api/templates")


@bp.get("/")
@require_auth
@openapi.tag("Templates")
@openapi.summary("List active templates")
async def get_templates(request):
    templates = await list_templates()
    return json({"templates": templates})


@bp.post("/")
@require_auth
@require_permission("template:manage")
@openapi.tag("Templates")
@openapi.summary("Register a new template")
async def post_template(request):
    try:
        template_id = require_json_field(request.json, "template_id")
        config_yaml = require_json_field(request.json, "config_yaml")
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    description = (request.json or {}).get("description", "")
    result = await register_template(template_id, config_yaml, description)
    return json(result, status=201)
