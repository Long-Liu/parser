import logging
from datetime import datetime
from sanic import Request

logger = logging.getLogger("parser")


def register(app):
    """注册请求/响应日志中间件"""

    @app.middleware("request")
    async def log_request(request: Request):
        request.ctx.start_time = datetime.now()
        logger.info(f"> {request.method} {request.path} | from={request.client_ip}")

    @app.middleware("response")
    async def log_response(request: Request, response):
        start = getattr(request.ctx, "start_time", datetime.now())
        elapsed = (datetime.now() - start).total_seconds() * 1000
        status = response.status if hasattr(response, "status") else 200
        logger.info(f"< {request.method} {request.path} | {status} | {elapsed:.0f}ms")
