from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.dto import LoginCommand, RegisterCommand
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.domain.jwt_service import JwtService
from contexts.auth.infrastructure.repositories import UserRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("auth_ddd", url_prefix="/api")


def _auth_service(request) -> AuthApplicationService:
    cfg = request.app.ctx.config
    jwt_svc = JwtService(cfg.SECRET_KEY)
    return AuthApplicationService(
        user_repo=UserRepositoryImpl(),
        auth_service=AuthenticationService(),
        jwt_service=jwt_svc,
    )


@bp.post("/auth/login")
@openapi.tag("Auth")
@openapi.summary("Login")
async def login(request):
    data = request.json or {}
    svc = _auth_service(request)
    try:
        result = await svc.login(LoginCommand(
            username=data.get("username", ""), password=data.get("password", "")))
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
    svc = _auth_service(request)
    try:
        result = await svc.register(RegisterCommand(
            username=data.get("username", ""), password=data.get("password", ""),
            real_name=data.get("real_name", ""), email=data.get("email", ""),
            phone=data.get("phone", "")))
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)
