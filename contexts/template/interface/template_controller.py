from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.shared.domain.identifiers import TemplateId
from contexts.shared.domain.exceptions import DomainError
from contexts.template.application.template_app_service import TemplateApplicationService
from contexts.container import container
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("template_ddd", url_prefix="/api")


@bp.get("/templates")
@require_auth
@openapi.tag("Template")
@openapi.summary("List templates")
async def list_templates(request):
    svc = container.get(TemplateApplicationService)
    result = await svc.list_all()
    return json(result)


@bp.get("/templates/<template_id:str>")
@require_auth
@openapi.tag("Template")
@openapi.summary("Get template detail")
async def get_template(request, template_id: str):
    svc = container.get(TemplateApplicationService)
    try:
        result = await svc.get_by_id(TemplateId(template_id))
        return json(result)
    except DomainError as e:
        return error_to_response(e)
