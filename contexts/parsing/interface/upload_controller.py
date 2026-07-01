# ponytail: adapted from api/upload_api.py.

from __future__ import annotations

import os
from datetime import datetime

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("upload_ddd", url_prefix="/api")

ALLOWED_MIME_TYPES = frozenset({
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})
ALLOWED_EXTENSIONS = frozenset({".xlsx"})
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


@bp.post("/upload")
@require_auth
@require_permission("data:upload")
@openapi.tag("Upload")
@openapi.summary("Upload Excel file for parsing")
async def upload(request):
    if "file" not in request.files:
        return json({"error": "no file"}, status=400)

    file = request.files.get("file")
    if isinstance(file, list):
        file = file[0]
    if not file:
        return json({"error": "no file"}, status=400)

    if hasattr(file, "type") and file.type not in ALLOWED_MIME_TYPES:
        return json({"error": "only .xlsx files are accepted"}, status=400)
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return json({"error": "only .xlsx files are accepted"}, status=400)
    if hasattr(file, "body") and len(file.body) > MAX_UPLOAD_SIZE:
        return json({"error": "file exceeds 50MB limit"}, status=400)

    try:
        project_id = int(request.form.get("project_id", "0"))
    except (ValueError, TypeError):
        return json({"error": "invalid project_id"}, status=400)
    if project_id <= 0:
        return json({"error": "invalid project_id"}, status=400)

    ym = request.form.get("ym", datetime.now().strftime("%Y-%m"))
    user_id = getattr(request.ctx, "user_id", None)
    if user_id is None:
        return json({"error": "not authenticated"}, status=401)

    svc = UploadApplicationService()
    try:
        result = await svc.process(file, project_id, ym, user_id)
        if result["status"] == "failed":
            return json(
                dict(result, error="upload processing failed"), status=500
            )
        return json(result)
    except DomainError as e:
        return error_to_response(e)
