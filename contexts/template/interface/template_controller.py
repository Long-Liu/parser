from __future__ import annotations

from urllib.parse import quote

from sanic.response import raw
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.shared.domain.identifiers import TemplateId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from
from contexts.template.application.template_app_service import (
    TemplateApplicationService,
)

_XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


class TemplatesController(BaseController):
    name = "template_ddd"

    def __init__(self, template_svc: TemplateApplicationService):
        super().__init__()
        self.svc = template_svc

    def setup(self):
        self.bp.add_route(self.list_templates, "/templates",                   methods=["GET"])
        self.bp.add_route(self.get_template,   "/templates/<template_id:str>", methods=["GET"])
        self.bp.add_route(self.download_template,
                          "/templates/<template_id:str>/download",             methods=["GET"])

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

    @require_auth
    @openapi.tag("Template")
    @openapi.summary("Download template skeleton xlsx")
    async def download_template(self, request, template_id: str):
        content, filename = await self.svc.build_download(TemplateId(template_id))
        # RFC 5987: ASCII fallback filename + percent-encoded UTF-8 filename*
        disposition = (
            f'attachment; filename="{template_id}.xlsx"; '
            f"filename*=UTF-8''{quote(filename)}"
        )
        return raw(content, content_type=_XLSX_CONTENT_TYPE,
                   headers={"Content-Disposition": disposition})
