from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import generate_token, hash_password, check_password
from parser.models.user import get_user_by_username, create_user

bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/login")
async def login(request):
    data = request.json
    username = data.get("username", "")
    password = data.get("password", "")
    pool = request.app.ctx.pool

    user = await get_user_by_username(pool, username)
    if not user or not check_password(password, user["password"]):
        return json({"error": "invalid credentials"}, status=401)
    if not user.get("is_active"):
        return json({"error": "account disabled"}, status=403)

    token = generate_token(user["id"], user["username"])
    return json({"token": token, "user": {"id": user["id"], "username": user["username"], "real_name": user.get("real_name")}})


@bp.post("/register")
async def register(request):
    data = request.json
    pool = request.app.ctx.pool
    hashed = hash_password(data["password"])
    uid = await create_user(pool, data["username"], hashed, data.get("real_name"), data.get("email"), data.get("phone"))

    # Assign default admin role to first user, viewer to others
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM users")
            user_count = (await cur.fetchone())[0]
            role_code = "admin" if user_count == 1 else "viewer"
            await cur.execute("SELECT id FROM roles WHERE code=%s", (role_code,))
            role_row = await cur.fetchone()
            if role_row:
                await cur.execute("INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)", (uid, role_row[0]))

    return json({"id": uid, "username": data["username"], "role": role_code}, status=201)
