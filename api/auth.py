from sanic import Blueprint
from sanic.response import json
from sqlalchemy import text
from parser.middleware.auth import generate_token, hash_password, check_password
from parser.models.user import get_user_by_username, create_user

bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/login")
async def login(request):
    data = request.json
    session = request.app.ctx.Session()
    try:
        user = await get_user_by_username(session, data.get("username", ""))
        if not user or not check_password(data.get("password", ""), user.password):
            return json({"error": "invalid credentials"}, status=401)
        if not user.is_active:
            return json({"error": "account disabled"}, status=403)
        token = generate_token(user.id, user.username)
        return json({"token": token, "user": {"id": user.id, "username": user.username, "real_name": user.real_name}})
    finally:
        await session.close()


@bp.post("/register")
async def register(request):
    data = request.json
    session = request.app.ctx.Session()
    hashed = hash_password(data["password"])
    try:
        async with session.begin():
            uid = await create_user(session, data["username"], hashed,
                                     data.get("real_name"), data.get("email"), data.get("phone"))
            # Assign role: admin for first user, viewer for others
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            role_code = "admin" if user_count == 1 else "viewer"
            await session.execute(
                text("INSERT IGNORE INTO user_roles (user_id, role_id) SELECT :uid, id FROM roles WHERE code=:rc"),
                {"uid": uid, "rc": role_code},
            )
        return json({"id": uid, "username": data["username"], "role": role_code}, status=201)
    except Exception as e:
        return json({"error": str(e)}, status=400)
    finally:
        await session.close()
