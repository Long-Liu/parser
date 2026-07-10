from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.container import container

bp = Blueprint("users", url_prefix="/api")


@bp.get("/users")
@require_auth
@require_permission("user:manage")
@openapi.tag("Users")
@openapi.summary("List personnel")
async def list_users(request):
    svc = container.get(UserApplicationService)
    return json({"users": await svc.list_all()})
