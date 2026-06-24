import os
import aiomysql
from sanic import Sanic


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "excel_parser"),
    "autocommit": True,
    "minsize": 2,
    "maxsize": 10,
}


async def get_pool(app: Sanic = None) -> aiomysql.Pool:
    if app and hasattr(app.ctx, "pool"):
        return app.ctx.pool
    pool = await aiomysql.create_pool(**DB_CONFIG)
    if app:
        app.ctx.pool = pool
    return pool
