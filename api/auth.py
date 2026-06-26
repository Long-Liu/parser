import asyncio
import logging

import sqlalchemy as sa
from sanic import Blueprint
from sanic.response import json

from db.connection import execute, Transaction
from db.tables import users
from middleware.auth import generate_token, hash_password, check_password
from repositories.user import get_user_by_username

logger = logging.getLogger("parser.auth")
bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/login")
async def login(request):
    data = request.json
    if data is None:
        return json({"error": "invalid request body"}, status=400)
    cfg = request.app.ctx.config
    user = await get_user_by_username(data.get("username", ""))
    if not user or not check_password(data.get("password", ""), user["password"]):
        return json({"error": "invalid credentials"}, status=401)
    if not user.get("is_active"):
        return json({"error": "account disabled"}, status=403)
    token = generate_token(user["id"], user["username"], cfg.SECRET_KEY, cfg.JWT_EXPIRY_HOURS)
    return json({"token": token, "user": {"id": user["id"], "username": user["username"], "real_name": user.get("real_name")}})


@bp.post("/register")
async def register(request):
    data = request.json
    if data is None:
        return json({"error": "invalid request body"}, status=400)
    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        return json({"error": "username and password are required"}, status=400)
    if len(password) < 8:
        return json({"error": "password must be at least 8 characters"}, status=400)

    # check existence outside transaction — cheap, avoids holding locks
    result = await execute(
        users.select().where(users.c.username == username)
    )
    if await result.fetchone():
        return json({"error": "username already exists"}, status=409)

    hashed = hash_password(password)
    try:
        # create user + assign role in a SINGLE transaction to prevent ghost users
        # and TOCTOU race on first-user-admin detection
        async with Transaction() as conn:
            result = await conn.execute(
                users.insert().values(
                    username=username, password=hashed,
                    real_name=data.get("real_name"),
                    email=data.get("email"),
                    phone=data.get("phone"),
                )
            )
            uid = result.lastrowid

            crow = await (await conn.execute(
                sa.select(sa.func.count().label("cnt")).select_from(users).with_for_update()
            )).fetchone()
            user_count = crow[0] if crow else 0
            role_code = "admin" if user_count == 1 else "viewer"
            await conn.execute(
                sa.text(
                    "INSERT IGNORE INTO user_roles (user_id, role_id) "
                    "SELECT :uid, id FROM roles WHERE code=:code"
                ),
                {"uid": uid, "code": role_code},
            )
        return json({"id": uid, "username": username, "role": role_code}, status=201)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("registration failed for user %s", username)
        return json({"error": "registration failed"}, status=500)
