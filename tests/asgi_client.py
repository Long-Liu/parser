"""Minimal ASGI request client shared by the endpoint smoke tests.

Drives one request through a Sanic ASGI app directly (no live server),
returning ``(status_code, raw_body)``. Kept in one place so the various
``_asgi_get`` / ``_asgi_post`` helpers used across test files do not drift.
"""

from __future__ import annotations

import json

from sanic import Sanic


async def request(
    app: Sanic,
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int | None, bytes]:
    """Send one HTTP request to an ASGI-ready Sanic app."""
    status: dict = {}
    resp_body = bytearray()
    payload = b""
    headers: list[tuple[bytes, bytes]] = []
    if body is not None:
        payload = json.dumps(body).encode()
        headers.append((b"content-type", b"application/json"))
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            resp_body.extend(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
    }
    await app(scope, receive, send)
    return status.get("code"), bytes(resp_body)


async def get(app: Sanic, path: str, token: str | None = None) -> tuple[int | None, bytes]:
    return await request(app, "GET", path, token=token)


async def post(app: Sanic, path: str, body: dict, token: str | None = None) -> tuple[int | None, bytes]:
    return await request(app, "POST", path, body=body, token=token)
