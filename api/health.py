from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

bp = Blueprint("health")


@bp.get("/health")
@openapi.tag("Health")
@openapi.summary("Health check")
async def health(request):
    return json({"status": "ok", "env": "local" if request.app.ctx.config.DEBUG else "production"})
