from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.shared.domain.identifiers import TemplateId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from
from contexts.shared.interface.rest_controller import rest_controller
from contexts.template.application.template_app_service import (
    TemplateApplicationService,
)


@rest_controller("/api")
class TemplatesController(BaseController):
    name = "template_ddd"

    def __init__(self, template_svc: TemplateApplicationService):
        super().__init__()
        self.svc = template_svc

    def setup(self):
        self.bp.add_route(self.list_templates, "/templates",                   methods=["GET"])
        self.bp.add_route(self.get_template,   "/templates/<template_id:str>", methods=["GET"])

    @require_auth
    @openapi.tag("Template")
    @openapi.summary("List templates")
    async def list_templates(self, request):
        return self.json(await self.svc.list_all(pagination_from(request)))

    @require_auth
    @openapi.tag("Template")
    @openapi.summary("Get template detail")
    async def get_template(self, request, template_id: str):
        return self.json(await self.svc.get_by_id(TemplateId(template_id)))
