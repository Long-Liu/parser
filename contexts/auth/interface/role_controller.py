from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.container import container
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("roles", url_prefix="/api")


@bp.get("/roles")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("List all roles")
async def list_roles(request):
    svc = container.role_service()
    try:
        roles = await svc.list_all()
        return json({"roles": roles})
    except DomainError as e:
        return error_to_response(e)


@bp.post("/roles")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("Create a role")
async def create_role(request):
    data = request.json or {}
    svc = container.role_service()
    try:
        result = await svc.create(
            code=data.get("code", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            permission_codes=data.get("permissions", []),
        )
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)


@bp.get("/roles/<role_id:int>")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("Get role detail")
async def get_role(request, role_id: int):
    svc = container.role_service()
    try:
        return json(await svc.get(role_id))
    except DomainError as e:
        return error_to_response(e)


@bp.put("/roles/<role_id:int>")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("Update a role")
async def update_role(request, role_id: int):
    data = request.json or {}
    svc = container.role_service()
    try:
        result = await svc.update(
            role_id=role_id,
            name=data.get("name", ""),
            description=data.get("description", ""),
            permission_codes=data.get("permissions"),
        )
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.delete("/roles/<role_id:int>")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("Delete a role")
async def delete_role(request, role_id: int):
    svc = container.role_service()
    try:
        await svc.delete(role_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)


@bp.post("/users/<user_id:int>/roles/<role_id:int>")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("Assign a role to a user")
async def assign_role(request, user_id: int, role_id: int):
    svc = container.role_service()
    try:
        await svc.assign_to_user(user_id, role_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)


@bp.delete("/users/<user_id:int>/roles/<role_id:int>")
@require_auth
@require_permission("admin:roles")
@openapi.tag("Roles")
@openapi.summary("Remove a role from a user")
async def remove_role(request, user_id: int, role_id: int):
    svc = container.role_service()
    try:
        await svc.remove_from_user(user_id, role_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)
