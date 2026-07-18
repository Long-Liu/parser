from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.dto import LoginCommand, RegisterCommand
from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.interface.auth_middleware import require_auth
from contexts.shared.interface.base_controller import BaseController


class AuthController(BaseController):
    name = "auth"

    def __init__(
        self, auth_svc: AuthApplicationService, user_svc: UserApplicationService
    ):
        super().__init__()
        self.auth_svc = auth_svc
        self.user_svc = user_svc

    def setup(self):
        self.bp.add_route(self.login, "/auth/login", methods=["POST"])
        self.bp.add_route(self.register, "/auth/register", methods=["POST"])
        self.bp.add_route(self.current_user, "/auth/me", methods=["GET"])

    @openapi.tag("Auth")
    @openapi.summary("Login")
    async def login(self, request):
        data = request.json or {}
        result = await self.auth_svc.login(
            LoginCommand(
                username=data.get("username", ""), password=data.get("password", "")
            )
        )
        return self.json(
            {
                "token": result.token,
                "user": {
                    "id": result.user_id,
                    "username": result.username,
                    "real_name": result.real_name,
                },
            }
        )

    @openapi.tag("Auth")
    @openapi.summary("Register")
    async def register(self, request):
        data = request.json or {}
        result = await self.auth_svc.register(
            RegisterCommand(
                username=data.get("username", ""),
                password=data.get("password", ""),
                real_name=data.get("real_name", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                department=data.get("department", ""),
            )
        )
        return self.json(result, status=201)

    @require_auth
    async def current_user(self, request):
        return self.json(await self.user_svc.get(request.ctx.user_id))
