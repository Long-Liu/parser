from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.application.dto import LoginCommand, RegisterCommand
from contexts.container import container
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("auth_ddd", url_prefix="/api")


@bp.post("/auth/login")
@openapi.tag("Auth")
@openapi.summary("Login")
async def login(request):
    data = request.json or {}
    svc = container.authentication_service(request.app.ctx.config.SECRET_KEY)
    try:
        result = await svc.login(LoginCommand(
            username=data.get("username", ""),
            password=data.get("password", "")))
        return json({"token": result.token, "user": {
            "id": result.user_id, "username": result.username,
            "real_name": result.real_name}})
    except DomainError as e:
        return error_to_response(e)


@bp.post("/auth/register")
@openapi.tag("Auth")
@openapi.summary("Register")
async def register(request):
    data = request.json or {}
    svc = container.authentication_service(request.app.ctx.config.SECRET_KEY)
    try:
        result = await svc.register(RegisterCommand(
            username=data.get("username", ""),
            password=data.get("password", ""),
            real_name=data.get("real_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", "")))
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)
