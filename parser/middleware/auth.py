import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from sanic.response import json


JWT_SECRET = "change-me-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def generate_token(user_id: int, username: str, secret: str = None, expiry_seconds: int = None) -> str:
    s = secret or JWT_SECRET
    if expiry_seconds is not None:
        exp = datetime.utcnow() + timedelta(seconds=expiry_seconds)
    else:
        exp = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {"user_id": user_id, "username": username, "exp": exp}
    return jwt.encode(payload, s, algorithm=JWT_ALGORITHM)


def verify_token(token: str, secret: str = None) -> dict:
    s = secret or JWT_SECRET
    return jwt.decode(token, s, algorithms=[JWT_ALGORITHM])


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
        try:
            payload = verify_token(token)
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
                    row = await cur.fetchone()
                    if not row:
                        return json({"error": f"missing permission: {perm_code}"}, status=403)
            return await f(request, *args, **kwargs)
        return decorated
    return decorator
