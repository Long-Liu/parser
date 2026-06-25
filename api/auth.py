from sanic import Blueprint
from sanic.response import json
from middleware.auth import generate_token, hash_password, check_password
from repositories.user import get_user_by_username, create_user

bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/login")
async def login(request):
    data = request.json
    cfg = request.app.ctx.config
    pool = request.app.ctx.pool
    user = await get_user_by_username(pool, data.get("username", ""))
    if not user or not check_password(data.get("password", ""), user["password"]):
        return json({"error": "invalid credentials"}, status=401)
    if not user.get("is_active"):
        return json({"error": "account disabled"}, status=403)
    token = generate_token(user["id"], user["username"], cfg.SECRET_KEY, cfg.JWT_EXPIRY_HOURS)
    return json({"token": token, "user": {"id": user["id"], "username": user["username"], "real_name": user.get("real_name")}})


@bp.post("/register")
async def register(request):
    data = request.json
    pool = request.app.ctx.pool
    hashed = hash_password(data["password"])
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                uid = await create_user(pool, data["username"], hashed,
                                        data.get("real_name"), data.get("email"), data.get("phone"))
                await cur.execute("SELECT COUNT(*) FROM users")
                user_count = (await cur.fetchone())[0]
                role_code = "admin" if user_count == 1 else "viewer"
                await cur.execute(
                    "INSERT IGNORE INTO user_roles (user_id, role_id) SELECT %s, id FROM roles WHERE code=%s",
                    (uid, role_code))
        return json({"id": uid, "username": data["username"], "role": role_code}, status=201)
    except Exception as e:
        return json({"error": str(e)}, status=400)
