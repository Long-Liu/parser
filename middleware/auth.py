import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from sanic.response import json

JWT_ALGORITHM = "HS256"


def _get_config(request):
    return request.app.ctx.config


def generate_token(user_id: int, username: str, secret: str, expiry_hours: int = 24) -> str:
    exp = datetime.utcnow() + timedelta(hours=expiry_hours)
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


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(request, *args, **kwargs):
            user_id = getattr(request.ctx, "user_id", None)
            if not user_id:
                return json({"error": "not authenticated"}, status=401)
            pool = request.app.ctx.pool
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """SELECT 1 FROM user_roles ur
                           JOIN role_permissions rp ON ur.role_id = rp.role_id
                           JOIN permissions p ON rp.permission_id = p.id
                           WHERE ur.user_id = %s AND p.code = %s LIMIT 1""",
                        (user_id, perm_code),
                    )
                    if not await cur.fetchone():
                        return json({"error": f"missing permission: {perm_code}"}, status=403)
            return await f(request, *args, **kwargs)
        return decorated
    return decorator
