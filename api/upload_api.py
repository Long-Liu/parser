"""Upload endpoint — thin controller."""

import os
from datetime import datetime

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from middleware.auth import require_auth, require_permission
from services.upload_service import process_upload
from utils.validators import (get_query_int, ALLOWED_MIME_TYPES,
                               ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE)

bp = Blueprint("upload", url_prefix="/api")


@bp.post("/upload")
@require_auth
@require_permission("data:upload")
@openapi.tag("Upload")
@openapi.summary("Upload Excel file for parsing")
@openapi.description("Upload .xlsx file. Each sheet is matched to a template and data is extracted.")
async def upload(request):
    if "file" not in request.files:
        return json({"error": "no file"}, status=400)

    file = request.files.get("file")
    if isinstance(file, list):
        file = file[0]
    if not file:
        return json({"error": "no file"}, status=400)

    if file.type not in ALLOWED_MIME_TYPES:
        return json({"error": "only .xlsx files are accepted"}, status=400)
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return json({"error": "only .xlsx files are accepted"}, status=400)
    if hasattr(file, "body") and len(file.body) > MAX_UPLOAD_SIZE:
        return json({"error": "file exceeds 50MB limit"}, status=400)

    try:
        project_id = get_query_int(request.form, "project_id")
    except ValueError as e:
        return json({"error": str(e)}, status=400)
    if project_id is None or project_id <= 0:
        return json({"error": "invalid project_id"}, status=400)

    ym = request.form.get("ym", datetime.now().strftime("%Y-%m"))
    user_id = getattr(request.ctx, "user_id", None)
    if user_id is None:
        return json({"error": "not authenticated"}, status=401)

    result = await process_upload(file, project_id, ym, user_id)
    if result["status"] == "failed":
        return json(dict(result, error="upload processing failed"), status=500)
    return json(result)
