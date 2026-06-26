"""JWT auth + permission decorators for Sanic routes."""

from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from sanic.response import json

from db.connection import execute
from db.tables import user_roles, role_permissions, permissions

JWT_ALGORITHM = "HS256"


def _get_config(request):
    return request.app.ctx.config


def generate_token(user_id: int, username: str, secret: str, expiry_hours: int = 24) -> str:
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
        cfg = _get_config(request)
        try:
            payload = verify_token(token, cfg.SECRET_KEY)
            request.ctx.user_id = payload["user_id"]
            request.ctx.username = payload["username"]
        except jwt.ExpiredSignatureError:
            return json({"error": "token expired"}, status=401)
        except jwt.InvalidTokenError:
            return json({"error": "invalid token"}, status=401)
        return await f(request, *args, **kwargs)
    return decorated


def _fetch_user_id(request) -> int | None:
    user_id = getattr(request.ctx, "user_id", None)
    if user_id is not None:
        return user_id
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            cfg = _get_config(request)
            payload = verify_token(auth_header[7:], cfg.SECRET_KEY)
            return payload.get("user_id")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
    return None


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(request, *args, **kwargs):
            user_id = _fetch_user_id(request)
            if not user_id:
                return json({"error": "not authenticated"}, status=401)
            result = await execute(user_roles.select()
                .select_from(
                    user_roles
                    .join(role_permissions, user_roles.c.role_id == role_permissions.c.role_id)
                    .join(permissions, role_permissions.c.permission_id == permissions.c.id)
                )
                .where(
                    (user_roles.c.user_id == user_id)
                    & (permissions.c.code == perm_code)
                )
                .limit(1))
            if not await result.fetchone():
                return json({"error": f"missing permission: {perm_code}"}, status=403)
            return await f(request, *args, **kwargs)
        return decorated
    return decorator
