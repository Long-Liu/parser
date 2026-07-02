"""JWT auth + permission decorators for Sanic routes."""

from functools import wraps

from sanic.response import json

from contexts.shared.domain.exceptions import AuthenticationError
from contexts.container import container


def require_auth(f):
    @wraps(f)
    async def decorated(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return json({"error": "missing token"}, status=401)
        token = auth_header[7:]
        auth = container.request_authorization_service()
        try:
            ctx = await auth.authenticate(token)
        except AuthenticationError as e:
            return json({"error": str(e)}, status=401)
        request.ctx.user_id = ctx.user_id
        request.ctx.username = ctx.username
        request.ctx.permissions = ctx.permissions
        return await f(request, *args, **kwargs)
    return decorated


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(request, *args, **kwargs):
            permissions = getattr(request.ctx, "permissions", None)
            if permissions is None:
                return json({"error": "not authenticated"}, status=401)
            if perm_code not in permissions:
                return json(
                    {"error": f"missing permission: {perm_code}"}, status=403
                )
            return await f(request, *args, **kwargs)
        return decorated
    return decorator
