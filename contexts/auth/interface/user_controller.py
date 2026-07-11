from sanic_ext import openapi

from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from
from contexts.shared.interface.rest_controller import rest_controller


@rest_controller("/api")
class UsersController(BaseController):
    name = "users"

    def __init__(self, user_svc: UserApplicationService):
        super().__init__()
        self.svc = user_svc

    def setup(self):
        r = self.bp.add_route
        r(self.list_users,  "/users",                              methods=["GET"])
        r(self.create_user, "/users",                              methods=["POST"])
        r(self.get_user,    "/users/<user_id:int>",                methods=["GET"])
        r(self.update_user, "/users/<user_id:int>",                methods=["PUT"])
        r(self.delete_user, "/users/<user_id:int>",                methods=["DELETE"])
        r(self.reset_pw,    "/users/<user_id:int>/password",       methods=["PUT"])
        r(self.get_perms,   "/users/<user_id:int>/project-permissions", methods=["GET"])
        r(self.set_perms,   "/users/<user_id:int>/project-permissions", methods=["PUT"])

    @require_auth
    @require_permission("user:manage")
    @openapi.tag("Users")
    @openapi.summary("List personnel")
    async def list_users(self, request):
        p = pagination_from(request)
        return self.json(await self.svc.list_all(
            keyword=request.args.get("keyword", ""), page=p.page, size=p.size))

    @require_auth
    @require_permission("user:manage")
    async def create_user(self, request):
        data = request.json or {}
        result = await self.svc.create(
            username=data.get("username", ""), password=data.get("password", ""),
            real_name=data.get("real_name", ""), email=data.get("email", ""),
            phone=data.get("phone", ""), department=data.get("department", ""),
        )
        return self.json(result, status=201)

    @require_auth
    @require_permission("user:manage")
    async def get_user(self, request, user_id: int):
        return self.json(await self.svc.get(user_id))

    @require_auth
    @require_permission("user:manage")
    async def update_user(self, request, user_id: int):
        data = request.json or {}
        allowed = {k: data[k] for k in (
            "real_name", "email", "phone", "department", "is_active"
        ) if k in data}
        return self.json(await self.svc.update(user_id, **allowed))

    @require_auth
    @require_permission("user:manage")
    async def delete_user(self, request, user_id: int):
        await self.svc.delete(user_id)
        return self.json_ok()

    @require_auth
    @require_permission("user:manage")
    async def reset_pw(self, request, user_id: int):
        await self.svc.reset_password(
            user_id, (request.json or {}).get("password", ""))
        return self.json_ok()

    @require_auth
    @require_permission("user:manage")
    async def get_perms(self, request, user_id: int):
        return self.json(await self.svc.project_permissions(user_id))

    @require_auth
    @require_permission("user:manage")
    async def set_perms(self, request, user_id: int):
        permissions = (request.json or {}).get("permissions", [])
        return self.json(await self.svc.set_project_permissions(user_id, permissions))
