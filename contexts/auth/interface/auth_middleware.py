"""JWT auth + permission decorators for Sanic routes.

Dependency note: these decorators are applied statically at class-definition
time, so they cannot receive constructor-injected dependencies. Services are
resolved from ``request.app.ctx.services`` — Sanic's idiomatic application
container, populated by the composition root — rather than a hand-rolled
service locator. This is an intentional design decision: the alternative
(request-scoped factories) would couple every route declaration to the
container, trading a small coupling here for a much larger one everywhere.
"""

from functools import wraps

from sanic.request import Request
from sanic.response import json

from contexts.auth.application.authorization_app_service import (
    AuthorizationApplicationService,
)
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.auth.interface.request_context import RequestAuth, current_auth
from contexts.auth.interface.request_services import RequestServices
from contexts.shared.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
)
from contexts.shared.domain.identifiers import UserId
from contexts.shared.interface.base_controller import error_to_response


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
        request.ctx.auth = RequestAuth(
            user_id=ctx.user_id,
            username=ctx.username,
            permissions=frozenset(ctx.permissions),
            claims=ctx.claims,
        )
        return await f(*args, **kwargs)

    return decorated


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            request = _extract_request(args)
            try:
                permissions = current_auth(request).permissions
            except AuthenticationError:
                return json({"error": "not authenticated"}, status=401)
            if perm_code not in permissions:
                return json({"error": f"missing permission: {perm_code}"}, status=403)
            return await f(*args, **kwargs)

        return decorated

    return decorator


def _require_access(
    *,
    id_key: str,
    id_label: str,
    policy_method: str,
    missing_response: str | None,
    handle_domain_error: bool,
    roles: set[str] | None,
):
    """Shared implementation for project/batch access decorators."""

    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            request = _extract_request(args)
            permissions = set(current_auth(request).permissions)
            if ProjectAccessPolicy.has_elevated_permission(permissions):
                return await f(*args, **kwargs)
            raw = kwargs.get(id_key)
            if raw is None:
                raw = (request.args or {}).get(id_key) or (request.form or {}).get(id_key)
            if raw is None and missing_response is not None:
                return json({"error": missing_response}, status=400)
            try:
                services: RequestServices = request.app.ctx.services
                policy: ProjectAccessPolicy = services.project_access
                await getattr(policy, policy_method)(
                    UserId(current_auth(request).user_id),
                    int(raw or ""),
                    roles,
                )
            except (TypeError, ValueError):
                return json({"error": f"valid {id_label} is required"}, status=400)
            except AuthorizationError as exc:
                return json({"error": str(exc)}, status=403)
            except DomainError as exc:
                if handle_domain_error:
                    return error_to_response(exc)
                raise
            return await f(*args, **kwargs)

        return decorated

    return decorator


def require_project_access(*, roles: set[str] | None = None):
    """Require membership of the project identified by route, query or form."""
    return _require_access(
        id_key="project_id",
        id_label="project_id",
        policy_method="require",
        missing_response=None,
        handle_domain_error=False,
        roles=roles,
    )


def require_batch_access(*, roles: set[str] | None = None):
    return _require_access(
        id_key="batch_id",
        id_label="batch_id",
        policy_method="require_batch",
        missing_response="batch_id is required",
        handle_domain_error=True,
        roles=roles,
    )
