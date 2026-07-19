"""JWT auth + permission decorators for Sanic routes."""

from functools import wraps

from sanic.response import json

from contexts.auth.application.authorization_app_service import AuthorizationApplicationService
from contexts.shared.domain.exceptions import AuthenticationError, AuthorizationError, DomainError
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.shared.domain.identifiers import UserId
from contexts.shared.interface.request_services import RequestServices


def _resolve_request(args):
    """Normalize dispatch args for bound controller methods and plain functions.

    Sanic stores ``self.handler`` (a bound method) and calls it as
    ``handler(request, **match_info)``.  Because these decorators are applied
    to the unbound function at class-definition time, the wrapper receives
    ``(controller_instance, request, ...)`` for method routes, but
    ``(request, ...)`` for plain function routes.  Detect the request by its
    ``headers`` attribute so both dispatch styles work.
    """
    if not args:
        raise TypeError("route handler called without arguments")
    first, *rest = args
    if hasattr(first, "headers"):
        return (), first, tuple(rest)
    if rest and hasattr(rest[0], "headers"):
        return (first,), rest[0], tuple(rest[1:])
    return (), first, tuple(rest)


def require_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        prefix, request, rest = _resolve_request(args)
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
        return await f(*prefix, request, *rest, **kwargs)
    return decorated


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            prefix, request, rest = _resolve_request(args)
            permissions = getattr(request.ctx, "permissions", None)
            if permissions is None:
                return json({"error": "not authenticated"}, status=401)
            if perm_code not in permissions:
                return json(
                    {"error": f"missing permission: {perm_code}"}, status=403
                )
            return await f(*prefix, request, *rest, **kwargs)
        return decorated
    return decorator


def require_project_access(*, roles: set[str] | None = None):
    """Require membership of the project identified by route, query or form."""
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            prefix, request, rest = _resolve_request(args)
            permissions = set(getattr(request.ctx, "permissions", set()) or set())
            if "admin:roles" in permissions or "user:manage" in permissions:
                return await f(*prefix, request, *rest, **kwargs)
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
            return await f(*prefix, request, *rest, **kwargs)
        return decorated
    return decorator


def require_batch_access(*, roles: set[str] | None = None):
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            prefix, request, rest = _resolve_request(args)
            permissions = set(getattr(request.ctx, "permissions", set()) or set())
            if "admin:roles" in permissions or "user:manage" in permissions:
                return await f(*prefix, request, *rest, **kwargs)
            try:
                services: RequestServices = request.app.ctx.services
                policy: ProjectAccessPolicy = services.project_access
                await policy.require_batch(
                    UserId(int(request.ctx.user_id)), int(kwargs["batch_id"]), roles,
                )
            except AuthorizationError as exc:
                return json({"error": str(exc)}, status=403)
            except DomainError as exc:
                return json({"error": str(exc)}, status=404)
            return await f(*prefix, request, *rest, **kwargs)
        return decorated
    return decorator
