from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.application.role_app_service import RoleApplicationService
from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from
from contexts.shared.interface.rest_controller import rest_controller


@rest_controller("/api")
class RolesController(BaseController):
    name = "roles"

    def __init__(self, role_svc: RoleApplicationService):
        super().__init__()
        self.svc = role_svc

    def setup(self):
        r = self.bp.add_route
        r(self.list_roles,     "/roles",                              methods=["GET"])
        r(self.create_role,    "/roles",                              methods=["POST"])
        r(self.get_role,       "/roles/<role_id:int>",                methods=["GET"])
        r(self.update_role,    "/roles/<role_id:int>",                methods=["PUT"])
        r(self.delete_role,    "/roles/<role_id:int>",                methods=["DELETE"])
        r(self.assign_role,    "/users/<user_id:int>/roles/<role_id:int>", methods=["POST"])
        r(self.remove_role,    "/users/<user_id:int>/roles/<role_id:int>", methods=["DELETE"])
        r(self.set_user_roles, "/users/<user_id:int>/roles",           methods=["PUT"])

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("List all roles")
    async def list_roles(self, request):
        p = pagination_from(request)
        return self.json(await self.svc.list_all(p.page, p.size))

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Create a role")
    async def create_role(self, request):
        data = request.json or {}
        result = await self.svc.create(
            code=data.get("code", ""), name=data.get("name", ""),
            description=data.get("description", ""),
            permission_codes=data.get("permissions", []),
        )
        return self.json(result, status=201)

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Get role detail")
    async def get_role(self, request, role_id: int):
        return self.json(await self.svc.get(role_id))

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Update a role")
    async def update_role(self, request, role_id: int):
        data = request.json or {}
        result = await self.svc.update(
            role_id=role_id, name=data.get("name", ""),
            description=data.get("description", ""),
            permission_codes=data.get("permissions"),
        )
        return self.json(result)

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Delete a role")
    async def delete_role(self, request, role_id: int):
        await self.svc.delete(role_id)
        return self.json_ok()

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Assign a role to a user")
    async def assign_role(self, request, user_id: int, role_id: int):
        await self.svc.assign_to_user(user_id, role_id)
        return self.json_ok()

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Remove a role from a user")
    async def remove_role(self, request, user_id: int, role_id: int):
        await self.svc.remove_from_user(user_id, role_id)
        return self.json_ok()

    @require_auth
    @require_permission("admin:roles")
    @openapi.tag("Roles")
    @openapi.summary("Replace all roles assigned to a user")
    async def set_user_roles(self, request, user_id: int):
        try:
            role_ids = [int(v) for v in (request.json or {}).get("role_ids", [])]
        except (TypeError, ValueError):
            from contexts.shared.domain.exceptions import ValidationError
            raise ValidationError("invalid role_ids") from None
        await self.svc.set_user_roles(user_id, role_ids)
        return self.json_ok()
