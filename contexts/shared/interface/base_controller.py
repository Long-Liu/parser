"""Base controller and shared error-handling utilities."""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import json

from contexts.shared.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)


class BaseController:
    """Base for all REST controllers.

    Subclasses define ``name`` (Blueprint name) and optionally ``url_prefix``.
    Routes are registered in ``setup()``, called after DI injection.

    Static helpers (usable as ``self.json_ok()``, ``self.error()``, etc.)::

        self.json(data)                        → json response, 200
        self.json(data, status=201)            → json response, custom status
        self.json_ok()                         → {"ok": True}
        self.error(ValidationError("bad"))     → {"error": "bad"}, 400
    """

    # ── subclasses must set ──────────────────────────────────────────

    name: str = ""
    url_prefix: str = "/api"

    def __init__(self) -> None:
        if not self.name:
            raise RuntimeError(f"{type(self).__name__} must set 'name'")
        self.bp = Blueprint(self.name, url_prefix=self.url_prefix)

    def setup(self) -> None:
        """Register routes on ``self.bp``.  Called after DI constructor injection."""
        raise NotImplementedError

    # ── response helpers (static — callable on class or instance) ────

    @staticmethod
    def json(data: dict | list, status: int = 200):
        return json(data, status=status)

    @staticmethod
    def json_ok():
        return json({"ok": True})

    @staticmethod
    def error(exc: DomainError):
        status_map = {
            ValidationError: 400,
            AuthenticationError: 401,
            AuthorizationError: 403,
            NotFoundError: 404,
            ConflictError: 409,
        }
        http_status = next(
            (status for error_type, status in status_map.items()
             if isinstance(exc, error_type)),
            500,
        )
        return json({"error": str(exc)}, status=http_status)


# ── module-level aliases for external callers (application.py) ─────

error_to_response = BaseController.error
