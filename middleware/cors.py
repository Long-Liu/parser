from datetime import datetime
from sanic import Request
from sanic.response import json


def register(app):
    """注册 CORS 中间件"""

    @app.middleware("request")
    async def cors_preflight(request: Request):
        if request.method == "OPTIONS":
            request.ctx.start_time = datetime.now()
            return json({}, headers={
                "Access-Control-Allow-Origin": request.headers.get("Origin", "*"),
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Max-Age": "3600",
            })

    @app.middleware("response")
    async def cors_headers(request: Request, response):
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
