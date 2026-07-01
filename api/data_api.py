from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from middleware.auth import require_auth, require_permission
from services.data_service import (
    create_data_row,
    delete_data_row,
    get_data,
    get_data_row,
    update_data_row,
)
from services.errors_service import ServiceError
from utils.validators import is_valid_template_id, get_query_int

bp = Blueprint("data", url_prefix="/api/data")


@bp.get("/<template_id>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Query template data")
@openapi.description("Paginated query of parsed Excel data by template type.")
async def get_data_route(request, template_id):
    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    try:
        page = get_query_int(request.args, "page", 1)
        size = get_query_int(request.args, "size", 200)
        batch_id = get_query_int(request.args, "batch_id")
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    if page < 1 or size < 1 or size > 1000:
        return json({"error": "page >= 1, 1 <= size <= 1000"}, status=400)

    try:
        result = await get_data(template_id, batch_id=batch_id, page=page, size=size)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)

    return json(dict(template_id=template_id, **result))


@bp.get("/<template_id>/<row_id:int>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Get one template data row")
async def get_data_row_route(request, template_id, row_id):
    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    try:
        row = await get_data_row(template_id, row_id)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json(dict(template_id=template_id, row=row))


@bp.post("/<template_id>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Create one template data row")
async def post_data_row(request, template_id):
    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    try:
        row = await create_data_row(template_id, request.json)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json(dict(template_id=template_id, row=row), status=201)


@bp.put("/<template_id>/<row_id:int>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Update one template data row")
async def put_data_row(request, template_id, row_id):
    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    try:
        row = await update_data_row(template_id, row_id, request.json)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json(dict(template_id=template_id, row=row))


@bp.delete("/<template_id>/<row_id:int>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Delete one template data row")
async def delete_data_row_route(request, template_id, row_id):
    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    try:
        await delete_data_row(template_id, row_id)
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json({"deleted": True})
