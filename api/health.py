from sanic import Blueprint
from sanic.response import json

bp = Blueprint("health")


@bp.get("/health")
async def health(request):
    return json({"status": "ok", "env": request.app.ctx.config.DEBUG and "local" or "production"})
