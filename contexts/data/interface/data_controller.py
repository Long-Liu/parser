from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.infrastructure.repositories import DataQueryRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("data_ddd", url_prefix="/api")


@bp.get("/data/<template_id:str>")
@require_auth
@openapi.tag("Data")
@openapi.summary("Query parsed data")
async def query_data(request, template_id: str):
    batch_id = request.args.get("batch_id")
    batch_id = int(batch_id) if batch_id else None
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 200))
    svc = DataApplicationService(DataQueryRepositoryImpl())
    try:
        result = await svc.query(
            template_id, batch_id=batch_id, page=page, size=size,
        )
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.get("/data/<template_id:str>/<row_id:int>")
@require_auth
@openapi.tag("Data")
@openapi.summary("Get single data row")
async def get_data_row(request, template_id: str, row_id: int):
    svc = DataApplicationService(DataQueryRepositoryImpl())
    try:
        result = await svc.get_by_id(template_id, row_id)
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.delete("/data/<template_id:str>/<row_id:int>")
@require_auth
@openapi.tag("Data")
@openapi.summary("Delete data row")
async def delete_data_row(request, template_id: str, row_id: int):
    svc = DataApplicationService(DataQueryRepositoryImpl())
    try:
        await svc.delete_by_id(template_id, row_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)
