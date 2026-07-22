from __future__ import annotations

from sanic import Blueprint
from sanic.response import empty, json
from sanic_ext import openapi

bp = Blueprint("health")


@bp.get("/favicon.ico")
@openapi.exclude(True)
async def favicon(request):
    """Browsers request this automatically when opening Swagger UI."""
    return empty(status=204)


@bp.get("/health")
@openapi.tag("系统状态")
@openapi.summary("健康检查")
@openapi.description("检查 API 服务是否可以正常响应。")
@openapi.response(
    200,
    {"application/json": {"status": str, "env": str}},
    "服务运行正常",
)
async def health(request):
    return json({"status": "ok", "env": "local" if request.app.ctx.settings.debug else "production"})
