from __future__ import annotations

from sanic.response import json
from sanic_ext import openapi

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.dto import LoginCommand, RegisterCommand
from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.interface.auth_middleware import require_auth
from contexts.auth.interface.request_services import RequestServices
from contexts.shared.domain.exceptions import AuthenticationError
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
        self.bp.add_route(self.change_password, "/auth/change-password", methods=["POST"])
        self.bp.add_route(self.logout, "/auth/logout", methods=["POST"])

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
        # Registration gate: when auth.allow_open_register is false (default),
        # only callers with the user:manage permission may create accounts —
        # same 401/403 semantics as require_auth + require_permission.
        if not _open_registration_allowed(request):
            denied = await _require_user_manage(request)
            if denied is not None:
                return denied
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

    @require_auth
    @openapi.tag("Auth")
    @openapi.summary("Change own password")
    async def change_password(self, request):
        data = request.json or {}
        await self.auth_svc.change_password(
            user_id=request.ctx.user_id,
            old_password=data.get("old_password", ""),
            new_password=data.get("new_password", ""),
        )
        return self.json_ok()

    @require_auth
    @openapi.tag("Auth")
    @openapi.summary("Logout (revoke current token)")
    async def logout(self, request):
        claims = getattr(request.ctx, "token_claims", {}) or {}
        await self.auth_svc.logout(
            user_id=request.ctx.user_id,
            token_jti=claims.get("jti"),
            token_exp=claims.get("exp"),
        )
        return self.json_ok()


def _open_registration_allowed(request) -> bool:
    settings = getattr(request.app.ctx, "settings", None)
    auth_config = getattr(settings, "auth", None)
    return bool(getattr(auth_config, "allow_open_register", False))


async def _require_user_manage(request):
    """Inline require_auth + require_permission('user:manage'); None when allowed."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return json({"error": "missing token"}, status=401)
    services: RequestServices = request.app.ctx.services
    try:
        ctx = await services.authorization.authenticate(auth_header[7:])
    except AuthenticationError as e:
        return json({"error": str(e)}, status=401)
    if "user:manage" not in ctx.permissions:
        return json({"error": "missing permission: user:manage"}, status=403)
    return None
