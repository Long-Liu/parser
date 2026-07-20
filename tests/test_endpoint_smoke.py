"""Smoke tests for HTTP endpoints — no MySQL required.

- /health runs on a standalone Sanic app (no create_app → no DB listeners).
- AnalyticsController handlers are invoked through their undecorated functions
  with fake services, asserting that Pagination objects are passed through
  instead of being split into page/size scalars.
"""

import json as std_json
from types import SimpleNamespace

from sanic import Sanic

from contexts.analytics.interface.analytics_controller import AnalyticsController
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.config import Settings
from contexts.shared.interface.health_controller import bp as health_bp

# ── minimal ASGI client ─────────────────────────────────────────────────────


async def _asgi_get(app, path: str):
    status: dict = {}
    body = bytearray()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
    }
    await app(scope, receive, send)
    return status.get("code"), bytes(body)


# ── /health ──────────────────────────────────────────────────────────────────


def _health_app(debug: bool) -> Sanic:
    app = Sanic(f"health_smoke_{debug}")
    app.asgi = True  # allow direct ASGI calls without app.run()
    app.ctx.settings = Settings(debug=debug)
    app.blueprint(health_bp)
    app.finalize()
    app.signalize(allow_fail_builtin=False)  # treat unregistered built-in signals as no-ops
    return app


async def test_health_returns_200_and_local_env_when_debug():
    code, body = await _asgi_get(_health_app(debug=True), "/health")
    assert code == 200
    assert std_json.loads(body) == {"status": "ok", "env": "local"}


async def test_health_returns_production_env_when_not_debug():
    code, body = await _asgi_get(_health_app(debug=False), "/health")
    assert code == 200
    assert std_json.loads(body) == {"status": "ok", "env": "production"}


# ── AnalyticsController ─────────────────────────────────────────────────────


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


class FakeAnalyticsService:
    def __init__(self):
        self.calls = {}

    async def notifications(self, *args):
        self.calls["notifications"] = args
        return {"notifications": [], "unread": 0, "pagination": {}}

    async def project_profits(self, *args):
        self.calls["project_profits"] = args
        return {"projects": [], "pagination": {}}

    async def cost_details(self, *args):
        self.calls["cost_details"] = args
        return {"data": [], "pagination": {}}


class FakeAlertService:
    def __init__(self):
        self.calls = {}

    async def find(self, **kwargs):
        self.calls["find"] = kwargs
        return {"alerts": [], "pagination": {}}


def _controller():
    analytics = FakeAnalyticsService()
    alerts = FakeAlertService()
    return (
        AnalyticsController(analytics, SimpleNamespace(), alerts),
        analytics,
        alerts,
    )


def _request(**args):
    """Fake request: admin permissions short-circuit the project-scope lookup."""
    return SimpleNamespace(
        args=args,
        ctx=SimpleNamespace(user_id=7, permissions={"admin:roles"}),
    )


async def test_notifications_passes_pagination_object():
    controller, analytics, _ = _controller()
    request = _request(page="2", size="5", unread_only="true")

    response = await _unwrap(AnalyticsController.notifications)(controller, request)

    user_id, pagination, unread_only, project_ids = analytics.calls["notifications"]
    assert user_id == 7
    assert isinstance(pagination, Pagination)
    assert (pagination.page, pagination.size) == (2, 5)
    assert unread_only is True
    assert project_ids is None
    assert response.status == 200


async def test_project_profits_passes_pagination_object():
    controller, analytics, _ = _controller()
    request = _request(page="3", size="10", ym="2025-06")

    await _unwrap(AnalyticsController.project_profits)(controller, request)

    ym, pagination, project_ids = analytics.calls["project_profits"]
    assert ym == "2025-06"
    assert isinstance(pagination, Pagination)
    assert (pagination.page, pagination.size) == (3, 10)
    assert project_ids is None


async def test_cost_details_passes_pagination_object():
    controller, analytics, _ = _controller()
    request = _request(page="1", size="20", ym="2025-05")

    await _unwrap(AnalyticsController.cost_details)(controller, request, project_id=42)

    project_id, ym, pagination = analytics.calls["cost_details"]
    assert project_id == 42
    assert ym == "2025-05"
    assert isinstance(pagination, Pagination)
    assert (pagination.page, pagination.size) == (1, 20)


async def test_dashboard_alerts_uses_find_with_pagination_object():
    controller, _, alerts = _controller()
    request = _request(page="2", size="3", status="active", level="warning")

    response = await _unwrap(AnalyticsController.dashboard_alerts)(controller, request)

    call = alerts.calls["find"]
    assert call["project_ids"] is None
    assert call["status"] == "active"
    assert call["level"] == "warning"
    assert isinstance(call["pagination"], Pagination)
    assert (call["pagination"].page, call["pagination"].size) == (2, 3)
    assert response.status == 200
