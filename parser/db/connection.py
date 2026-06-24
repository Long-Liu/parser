import aiomysql
from sanic import Sanic


async def get_pool(app: Sanic = None) -> aiomysql.Pool:
    if app and hasattr(app.ctx, "pool"):
        return app.ctx.pool
    pool = await aiomysql.create_pool(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="",
        db="excel_parser",
        autocommit=True,
        minsize=2,
        maxsize=10,
    )
    if app:
        app.ctx.pool = pool
    return pool
