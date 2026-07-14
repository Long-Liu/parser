from __future__ import annotations

# CORS middleware with explicit origin allowlist.

from sanic import Request
from sanic.response import json

from contexts.shared.infrastructure.database.config import get_config


def _allowed_origins() -> frozenset[str]:
    raw = get_config("CORS_ORIGINS")
    return frozenset(o.strip() for o in raw.split(",") if o.strip())


def _cors_origin(request: Request) -> str:
    """Return the CORS origin value: '*' for wildcard, or matching request Origin."""
    allowed = _allowed_origins()
    if "*" in allowed:
        return "*"
    origin = request.headers.get("Origin", "")
    return origin if origin in allowed else ""


def register(app):
    """Register CORS middleware on a Sanic application."""

    @app.middleware("request")
    async def cors_preflight(request: Request):
        if request.method == "OPTIONS":
            return json({}, headers={
                "Access-Control-Allow-Origin": _cors_origin(request),
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Max-Age": "3600",
            })

    @app.middleware("response")
    async def cors_headers(request: Request, response):
        origin = _cors_origin(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
