from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.container import container
from contexts.shared.domain.exceptions import DomainError, ValidationError

bp = Blueprint("users", url_prefix="/api")


@bp.get("/users")
@require_auth
@require_permission("user:manage")
@openapi.tag("Users")
@openapi.summary("List personnel")
async def list_users(request):
    try:
        page = _parse_int(request.args.get("page"), 1)
        size = _parse_int(request.args.get("size"), 20)
        keyword = request.args.get("keyword", "")
        svc = container.get(UserApplicationService)
        return json(await svc.list_all(keyword=keyword, page=page, size=size))
    except DomainError as exc:
        return json({"error": str(exc)}, status=400)


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValidationError(f"invalid integer: {value}") from None
