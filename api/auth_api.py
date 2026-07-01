from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from services.auth_service import login as login_svc, register as register_svc
from services.errors_service import ServiceError

bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/login")
@openapi.tag("Auth")
@openapi.summary("User login")
@openapi.description("Returns a JWT token for valid credentials.")
async def login(request):
    data = request.json
    if data is None:
        return json({"error": "invalid request body"}, status=400)
    cfg = request.app.ctx.config
    try:
        result = await login_svc(
            data.get("username", ""), data.get("password", ""),
            cfg.SECRET_KEY, cfg.JWT_EXPIRY_HOURS,
        )
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json(result)


@bp.post("/register")
@openapi.tag("Auth")
@openapi.summary("User registration")
@openapi.description("First registered user becomes admin.")
async def register(request):
    try:
        result = await register_svc(request.json or {})
    except ServiceError as e:
        return json({"error": str(e)}, status=e.http_status)
    return json(result, status=201)
