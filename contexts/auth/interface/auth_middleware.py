"""JWT auth + permission decorators for Sanic routes.
Migrated from middleware/auth.py — now fully owned by Auth context."""

from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from sanic.response import json

from contexts.container import container

JWT_ALGORITHM = "HS256"


def generate_token(user_id: int, username: str, secret: str,
                   expiry_hours: int = 24) -> str:
    exp = datetime.now(tz=timezone.utc) + timedelta(hours=expiry_hours)
    payload = {"user_id": user_id, "username": username, "exp": exp}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def verify_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def require_auth(f):
    @wraps(f)
    async def decorated(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return json({"error": "missing token"}, status=401)
        token = auth_header[7:]
        cfg = request.app.ctx.config
        auth = container.authorization_service(cfg.SECRET_KEY)
        try:
            ctx = await auth.authenticate(token)
            request.ctx.user_id = ctx.user_id
            request.ctx.username = ctx.username
            request.ctx.permissions = ctx.permissions
        except jwt.ExpiredSignatureError:
            return json({"error": "token expired"}, status=401)
        except jwt.InvalidTokenError:
            return json({"error": "invalid token"}, status=401)
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
