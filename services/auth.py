"""Authentication service — login and registration business logic."""

import asyncio
import logging

from middleware.auth import generate_token, hash_password, check_password
from repositories.user import UserRepo
from services.errors import ServiceError, ConflictError

logger = logging.getLogger("parser.auth")


async def login(username: str, password: str, secret_key: str,
                jwt_expiry_hours: int) -> dict:
    """Return {token, user} on success."""
    user = await UserRepo.get_by_username(username)
    if not user or not check_password(password, user["password"]):
        raise ServiceError("invalid credentials", http_status=401)
    if not user.get("is_active"):
        raise ServiceError("account disabled", http_status=403)
    token = generate_token(user["id"], user["username"], secret_key, jwt_expiry_hours)
    return {
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "real_name": user.get("real_name")},
    }


async def register(data: dict) -> dict:
    """Register a new user. Returns {id, username, role}."""
    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        raise ServiceError("username and password are required")
    if len(password) < 8:
        raise ServiceError("password must be at least 8 characters")

    existing = await UserRepo.get_by_username(username)
    if existing:
        raise ConflictError("username already exists")

    hashed = hash_password(password)
    try:
        uid, role_code = await UserRepo.register(
            username, hashed,
            real_name=data.get("real_name"),
            email=data.get("email"),
            phone=data.get("phone"),
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("registration failed for user %s", username)
        raise ServiceError("registration failed", http_status=500) from None

    return {"id": uid, "username": username, "role": role_code}
