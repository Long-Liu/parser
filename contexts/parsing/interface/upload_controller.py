from __future__ import annotations

import os
from datetime import datetime

from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import (
    require_auth, require_permission, require_project_access, require_batch_access,
)
from contexts.parsing.application.dto import UploadedFile
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import parse_int
from contexts.shared.interface.rest_controller import rest_controller
from contexts.parsing.domain.upload_constraints import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_SIZE,
)


@rest_controller("/api")
class UploadsController(BaseController):
    name = "upload_ddd"

    def __init__(self, upload_svc: UploadApplicationService):
        super().__init__()
        self.svc = upload_svc

    def setup(self):
        self.bp.add_route(self.upload,           "/upload",                        methods=["POST"])
        self.bp.add_route(self.preview,          "/upload/preview",                methods=["POST"])
        self.bp.add_route(self.confirm,          "/upload/<batch_id:int>/confirm", methods=["POST"])
        self.bp.add_route(self.cancel,           "/upload/<batch_id:int>/preview", methods=["DELETE"])

    @require_auth
    @require_permission("data:upload")
    @require_project_access(roles={"manager"})
    @openapi.tag("Upload")
    @openapi.summary("Upload Excel file for parsing")
    async def upload(self, request):
        if "file" not in request.files:
            return self.error(ValidationError("no file"))

        file = request.files.get("file")
        if isinstance(file, list):
            file = file[0]
        if not file:
            return self.error(ValidationError("no file"))

        if hasattr(file, "type") and file.type not in ALLOWED_MIME_TYPES:
            return self.error(ValidationError("only .xlsx files are accepted"))
        _, ext = os.path.splitext(file.name.lower())
        if ext not in ALLOWED_EXTENSIONS:
            return self.error(ValidationError("only .xlsx files are accepted"))
        if hasattr(file, "body") and len(file.body) > MAX_UPLOAD_SIZE:
            return self.error(ValidationError("file exceeds 50MB limit"))

        project_id = ProjectId(parse_int(request.form.get("project_id"), 0))

        ym_str = request.form.get("ym", datetime.now().strftime("%Y-%m"))
        ym = YearMonth.parse(ym_str)

        user_id_raw = getattr(request.ctx, "user_id", None)
        if user_id_raw is None:
            return self.json({"error": "not authenticated"}, status=401)

        result = await self.svc.process(
            UploadedFile(name=file.name, body=file.body,
                         content_type=getattr(file, "type", "")),
            project_id, ym, UserId(user_id_raw),
        )
        if result["status"] == "failed":
            return self.json(dict(result, error="upload processing failed"), status=500)
        return self.json(result)

    @require_auth
    @require_permission("data:upload")
    @require_project_access(roles={"manager"})
    async def preview(self, request):
        file = request.files.get("file")
        if isinstance(file, list):
            file = file[0] if file else None
        if not file:
            return self.error(ValidationError("no file"))
        _, ext = os.path.splitext(file.name.lower())
        if ext not in ALLOWED_EXTENSIONS or len(file.body) > MAX_UPLOAD_SIZE:
            return self.error(ValidationError("invalid .xlsx file"))
        project_id = ProjectId(parse_int(request.form.get("project_id"), 0))
        ym = YearMonth.parse(request.form.get("ym", ""))
        result = await self.svc.preview(
            UploadedFile(file.name, file.body, getattr(file, "type", "")),
            project_id, ym, UserId(request.ctx.user_id),
        )
        return self.json(result)

    @require_auth
    @require_permission("data:upload")
    @require_batch_access(roles={"manager"})
    async def confirm(self, request, batch_id: int):
        return self.json(await self.svc.confirm(batch_id, UserId(request.ctx.user_id)))

    @require_auth
    @require_permission("data:upload")
    @require_batch_access(roles={"manager"})
    async def cancel(self, request, batch_id: int):
        await self.svc.cancel_preview(batch_id, UserId(request.ctx.user_id))
        return self.json_ok()
