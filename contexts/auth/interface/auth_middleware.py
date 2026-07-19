"""JWT auth + permission decorators for Sanic routes."""

from functools import wraps

from sanic.request import Request
from sanic.response import json

from contexts.auth.application.authorization_app_service import AuthorizationApplicationService
from contexts.shared.domain.exceptions import AuthenticationError, AuthorizationError, DomainError
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.shared.domain.identifiers import UserId
from contexts.shared.interface.base_controller import error_to_response
from contexts.auth.interface.request_services import RequestServices


def _extract_request(args: tuple) -> Request:
    """Return the Sanic request from view arguments.

    Supports both function views ``handler(request, ...)`` and class-based
    views ``handler(self, request, ...)``.
    """
    for arg in args[:2]:
        if isinstance(arg, Request):
            return arg
    raise RuntimeError("auth decorator could not locate the request argument")


def require_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        request = _extract_request(args)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return json({"error": "missing token"}, status=401)
        token = auth_header[7:]
        services: RequestServices = request.app.ctx.services
        auth: AuthorizationApplicationService = services.authorization
        try:
            ctx = await auth.authenticate(token)
        except AuthenticationError as e:
            return json({"error": str(e)}, status=401)
        request.ctx.user_id = ctx.user_id
        request.ctx.username = ctx.username
        request.ctx.permissions = ctx.permissions
        # Verified JWT claims (jti/iat/exp) for logout / change-password.
        request.ctx.token_claims = ctx.claims
        return await f(*args, **kwargs)
    return decorated


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            request = _extract_request(args)
            permissions = getattr(request.ctx, "permissions", None)
            if permissions is None:
                return json({"error": "not authenticated"}, status=401)
            if perm_code not in permissions:
                return json(
                    {"error": f"missing permission: {perm_code}"}, status=403
                )
            return await f(*args, **kwargs)
        return decorated
    return decorator


def require_project_access(*, roles: set[str] | None = None):
    """Require membership of the project identified by route, query or form."""
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            request = _extract_request(args)
            permissions = set(getattr(request.ctx, "permissions", set()) or set())
            if ProjectAccessPolicy.has_elevated_permission(permissions):
                return await f(*args, **kwargs)
            raw = kwargs.get("project_id")
            if raw is None:
                raw = request.args.get("project_id") or request.form.get("project_id")
            try:
                services: RequestServices = request.app.ctx.services
                policy: ProjectAccessPolicy = services.project_access
                await policy.require(
                    UserId(int(request.ctx.user_id)), int(raw), roles,
                )
            except (TypeError, ValueError):
                return json({"error": "valid project_id is required"}, status=400)
            except AuthorizationError as exc:
                return json({"error": str(exc)}, status=403)
            return await f(*args, **kwargs)
        return decorated
    return decorator


def require_batch_access(*, roles: set[str] | None = None):
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            request = _extract_request(args)
            permissions = set(getattr(request.ctx, "permissions", set()) or set())
            if ProjectAccessPolicy.has_elevated_permission(permissions):
                return await f(*args, **kwargs)
            raw = kwargs.get("batch_id")
            if raw is None:
                raw = request.args.get("batch_id") or request.form.get("batch_id")
            if raw is None:
                return json({"error": "batch_id is required"}, status=400)
            try:
                services: RequestServices = request.app.ctx.services
                policy: ProjectAccessPolicy = services.project_access
                await policy.require_batch(
                    UserId(int(request.ctx.user_id)), int(raw), roles,
                )
            except (TypeError, ValueError):
                return json({"error": "valid batch_id is required"}, status=400)
            except AuthorizationError as exc:
                return json({"error": str(exc)}, status=403)
            except DomainError as exc:
                return error_to_response(exc)
            return await f(*args, **kwargs)
        return decorated
    return decorator
