from __future__ import annotations

from sanic.response import json

from contexts.shared.domain.exceptions import (
    AuthenticationError, AuthorizationError, ConflictError,
    DomainError, NotFoundError, ValidationError,
)


def json_response(data: dict | list, status: int = 200):
    return json(data, status=status)


def error_to_response(exc: DomainError):
    status_map = {
        ValidationError: 400, AuthenticationError: 401,
        AuthorizationError: 403, NotFoundError: 404, ConflictError: 409,
    }
    http_status = status_map.get(type(exc), 500)
    return json({"error": str(exc)}, status=http_status)


def _demo():
    resp = json_response({"ok": True})
    assert resp.status == 200
    resp2 = error_to_response(NotFoundError("user 1"))
    assert resp2.status == 404
    print("base_controller: OK")


if __name__ == "__main__":
    _demo()
