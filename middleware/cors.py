"""CORS middleware with explicit origin allowlist."""

import os

from sanic import Request
from sanic.response import json

# Comma-separated allowed origins, default localhost on common dev ports
_RAW_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
ALLOWED_ORIGINS = frozenset(o.strip() for o in _RAW_ORIGINS.split(",") if o.strip())


def _safe_origin(request: Request) -> str:
    """Return the request Origin only if it is in the allowlist."""
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        return origin
    return ""


def register(app):
    """Register CORS middleware on a Sanic application."""

    @app.middleware("request")
    async def cors_preflight(request: Request):
        if request.method == "OPTIONS":
            return json({}, headers={
                "Access-Control-Allow-Origin": _safe_origin(request),
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Max-Age": "3600",
            })

    @app.middleware("response")
    async def cors_headers(request: Request, response):
        origin = _safe_origin(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
