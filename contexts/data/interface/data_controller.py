from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.domain.data_query import FilterCriterion
from contexts.shared.domain.exceptions import DomainError, ValidationError
from contexts.container import container
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("data_ddd", url_prefix="/api")


def _parse_int(value: str | None, default: int) -> int:
    """Parse an integer query parameter and reject malformed input."""
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValidationError(f"invalid integer: {value}") from None


def _parse_filters(request) -> list[FilterCriterion]:
    """Parse repeatable filter query params: filter=field:op:value"""
    filters: list[FilterCriterion] = []
    for raw in request.args.getlist("filter"):
        parts = raw.split(":", 2)
        if len(parts) == 3:
            filters.append(FilterCriterion(
                field=parts[0], operator=parts[1], value=parts[2],
            ))
    return filters


def _parse_int_or_none(value: str | None) -> int | None:
    """Parse an optional integer query parameter."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValidationError(f"invalid integer: {value}") from None


@bp.get("/data/<template_id:str>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Query parsed data")
async def query_data(request, template_id: str):
    try:
        batch_id = _parse_int_or_none(request.args.get("batch_id"))
        page = _parse_int(request.args.get("page"), 1)
        size = _parse_int(request.args.get("size"), 200)
        svc = container.get(DataApplicationService)
        result = await svc.query(
            template_id, batch_id=batch_id, page=page, size=size,
            filters=_parse_filters(request),
        )
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.get("/data/<template_id:str>/<row_id:int>")
@require_auth
@require_permission("data:view")
@openapi.tag("Data")
@openapi.summary("Get single data row")
async def get_data_row(request, template_id: str, row_id: int):
    svc = container.get(DataApplicationService)
    try:
        result = await svc.get_by_id(template_id, row_id)
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.delete("/data/<template_id:str>/<row_id:int>")
@require_auth
@require_permission("data:delete")
@openapi.tag("Data")
@openapi.summary("Delete data row")
async def delete_data_row(request, template_id: str, row_id: int):
    svc = container.get(DataApplicationService)
    try:
        await svc.delete_by_id(template_id, row_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)
