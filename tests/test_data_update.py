"""Tests for PUT /api/data/<template_id>/<row_id> (row field update)."""
import json as jsonlib
from types import SimpleNamespace

import pytest

from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.domain.data_query import DataRow
from contexts.data.domain.data_row_update import build_updates
from contexts.data.domain.repositories import DataQueryRepository
from contexts.data.interface.data_controller import DataController
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination


FIELD_TYPES = {
    "id": "other",
    "batch_id": "other",
    "hierarchy_code": "other",
    "budget_total": "decimal",
    "remark": "other",
    "monthly_data": "other",
    "created_at": "other",
}


# ── domain: build_updates ────────────────────────────────────────────

def test_build_updates_rejects_empty_fields():
    with pytest.raises(ValidationError, match="no fields"):
        build_updates(FIELD_TYPES, {})


def test_build_updates_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field: nope"):
        build_updates(FIELD_TYPES, {"nope": 1})


@pytest.mark.parametrize("protected", ["id", "batch_id"])
def test_build_updates_rejects_protected_fields(protected):
    with pytest.raises(ValidationError, match="protected"):
        build_updates(FIELD_TYPES, {protected: 1})


def test_build_updates_converts_decimal_and_keeps_plain_columns():
    updates = build_updates(
        FIELD_TYPES, {"budget_total": "12.50", "remark": "ok", "hierarchy_code": None}
    )
    assert updates == {"budget_total": 12.5, "remark": "ok", "hierarchy_code": None}


def test_build_updates_rejects_non_decimal_value_with_field_name():
    with pytest.raises(ValidationError, match="budget_total"):
        build_updates(FIELD_TYPES, {"budget_total": "not-a-number"})


def test_build_updates_accepts_decimal_none_as_null():
    assert build_updates(FIELD_TYPES, {"budget_total": None}) == {"budget_total": None}


def test_build_updates_monthly_data_must_be_dict():
    with pytest.raises(ValidationError, match="monthly_data"):
        build_updates(FIELD_TYPES, {"monthly_data": "not-a-dict"})


# ── application service (fake repository) ────────────────────────────

class FakeRepo(DataQueryRepository):
    def __init__(self, rows=None, field_types=None):
        self.rows = rows or {}
        self._field_types = field_types or {}
        self.applied = None

    async def query(self, template_id, batch_id, filters, pagination):
        return [], 0

    async def get_by_id(self, template_id: str, row_id: int):
        row = self.rows.get((template_id, row_id))
        return DataRow(fields=dict(row)) if row is not None else None

    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        self.rows.pop((template_id, row_id), None)

    async def field_types(self, template_id: str):
        if template_id not in self._field_types:
            raise NotFoundError(f"template {template_id} not found")
        return self._field_types[template_id]

    async def update_by_id(self, template_id: str, row_id: int, updates: dict) -> None:
        self.applied = updates
        self.rows[(template_id, row_id)].update(updates)


def _service_with_row(row):
    repo = FakeRepo(
        rows={("gross_profit", 5): row},
        field_types={"gross_profit": FIELD_TYPES},
    )
    return DataApplicationService(repo), repo


async def test_update_by_id_updates_columns_and_merges_monthly_data():
    svc, repo = _service_with_row({
        "id": 5, "batch_id": 7, "budget_total": 1.0,
        "monthly_data": {"2026-06_revenue": 100},
    })
    result = await svc.update_by_id("gross_profit", 5, {
        "budget_total": "99.5",
        "monthly_data": {"2026-07_revenue": 200},
    })
    assert repo.applied["budget_total"] == 99.5
    # merge, not replace: the pre-existing key survives
    assert repo.applied["monthly_data"] == {
        "2026-06_revenue": 100, "2026-07_revenue": 200,
    }
    assert result["budget_total"] == 99.5
    assert result["monthly_data"]["2026-06_revenue"] == 100
    assert result["monthly_data"]["2026-07_revenue"] == 200


async def test_update_by_id_merges_into_missing_monthly_data():
    svc, repo = _service_with_row({"id": 5, "batch_id": 7, "monthly_data": None})
    result = await svc.update_by_id("gross_profit", 5, {"monthly_data": {"a": 1}})
    assert result["monthly_data"] == {"a": 1}


async def test_update_by_id_unknown_field_raises_validation_error():
    svc, repo = _service_with_row({"id": 5, "batch_id": 7})
    with pytest.raises(ValidationError, match="unknown field"):
        await svc.update_by_id("gross_profit", 5, {"nope": 1})
    assert repo.applied is None


async def test_update_by_id_bad_decimal_raises_validation_error():
    svc, repo = _service_with_row({"id": 5, "batch_id": 7})
    with pytest.raises(ValidationError, match="budget_total"):
        await svc.update_by_id("gross_profit", 5, {"budget_total": "abc"})
    assert repo.applied is None


async def test_update_by_id_missing_row_raises_not_found():
    svc, _ = _service_with_row({"id": 5, "batch_id": 7})
    with pytest.raises(NotFoundError, match="row 999"):
        await svc.update_by_id("gross_profit", 999, {"remark": "x"})


async def test_update_by_id_unknown_template_raises_not_found():
    svc, _ = _service_with_row({"id": 5, "batch_id": 7})
    with pytest.raises(NotFoundError, match="template"):
        await svc.update_by_id("unknown", 5, {"remark": "x"})


# ── controller (undecorated handler + decorator contract) ────────────
#
# Handler bodies are tested via __wrapped__ unwrapping with fake requests.
# The 401/403 decorator contract is tested separately through a real Sanic
# app + ASGI call, because the auth decorators locate the request via
# isinstance(sanic.request.Request) (same style as tests/test_endpoint_smoke.py).

class FakeAuthorization:
    def __init__(self, permissions):
        self._permissions = permissions

    async def authenticate(self, token):
        return SimpleNamespace(
            user_id=1, username="tester", permissions=self._permissions,
            claims={"jti": "t", "iat": 0, "exp": 0},
        )


class FakeAccessPolicy:
    def __init__(self):
        self.calls = []

    async def require_data_row(self, user_id, template_id, row_id, roles=None):
        self.calls.append((user_id, template_id, row_id, roles))
        return 10


def _request(body=None, token="tok", permissions=None):
    req = SimpleNamespace()
    req.headers = {"Authorization": f"Bearer {token}"} if token else {}
    req.app = SimpleNamespace(ctx=SimpleNamespace(services=SimpleNamespace(
        authorization=FakeAuthorization(permissions if permissions is not None else set()),
    )))
    req.ctx = SimpleNamespace()
    req.json = body
    return req


def _controller():
    repo = FakeRepo(
        rows={("gross_profit", 5): {
            "id": 5, "batch_id": 7, "budget_total": 1.0,
            "monthly_data": {"2026-06_revenue": 100},
        }},
        field_types={"gross_profit": FIELD_TYPES},
    )
    access = FakeAccessPolicy()
    return DataController(DataApplicationService(repo), access), access


def _authed_request(controller, body, permissions=("data:upload",)):
    req = _request(body=body)
    req.ctx.user_id = 1
    req.ctx.username = "tester"
    req.ctx.permissions = set(permissions)
    return req


async def test_put_handler_returns_updated_row():
    controller, access = _controller()
    raw = DataController.update.__wrapped__.__wrapped__  # strip auth decorators
    req = _authed_request(controller, {
        "fields": {"budget_total": "99.5", "monthly_data": {"m": 2}},
    })
    resp = await raw(controller, req, template_id="gross_profit", row_id=5)
    assert resp.status == 200
    payload = jsonlib.loads(resp.body)
    assert payload["budget_total"] == 99.5
    assert payload["monthly_data"] == {"2026-06_revenue": 100, "m": 2}
    # batch access enforced via the row, manager role required
    (uid, tpl, rid, roles), = access.calls
    assert (uid.value, tpl, rid, roles) == (1, "gross_profit", 5, {"manager"})


async def test_put_handler_rejects_non_object_fields():
    controller, _ = _controller()
    raw = DataController.update.__wrapped__.__wrapped__
    req = _authed_request(controller, {"fields": "oops"})
    with pytest.raises(ValidationError, match="fields"):
        await raw(controller, req, template_id="gross_profit", row_id=5)


async def test_put_handler_missing_row_raises_not_found():
    controller, _ = _controller()
    raw = DataController.update.__wrapped__.__wrapped__
    req = _authed_request(controller, {"fields": {"remark": "x"}})
    with pytest.raises(NotFoundError, match="row 999"):
        await raw(controller, req, template_id="gross_profit", row_id=999)


# ── decorator contract via a real Sanic app (isinstance-based dispatch) ────


async def _asgi_get(app, path: str, token: str | None = None):
    """Minimal ASGI GET client (mirrors tests/test_endpoint_smoke.py)."""
    status: dict = {}
    body = bytearray()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    headers = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
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
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
    }
    await app(scope, receive, send)
    return status.get("code"), bytes(body)


def _protected_app(permissions, *, with_permission: bool):
    from sanic import Sanic
    from sanic.response import json

    from contexts.auth.interface.auth_middleware import (
        require_auth,
        require_permission,
    )

    app = Sanic(f"data_update_decorator_{with_permission}_{id(permissions)}")
    app.asgi = True
    app.ctx.services = SimpleNamespace(
        authorization=FakeAuthorization(permissions),
    )

    if with_permission:
        @app.get("/protected")
        @require_auth
        @require_permission("data:upload")
        async def protected(request):
            return json({"ok": True})
    else:
        @app.get("/protected")
        @require_auth
        async def protected(request):
            return json({"ok": True})

    app.finalize()
    app.signalize(allow_fail_builtin=False)
    return app


async def test_require_auth_decorator_returns_401_without_token():
    app = _protected_app(set(), with_permission=False)
    code, _ = await _asgi_get(app, "/protected", token=None)
    assert code == 401


async def test_require_permission_decorator_returns_403_without_data_upload():
    app = _protected_app({"data:view"}, with_permission=True)
    code, _ = await _asgi_get(app, "/protected", token="t")
    assert code == 403


async def test_decorator_chain_passes_with_data_upload_permission():
    app = _protected_app({"data:upload"}, with_permission=True)
    code, body = await _asgi_get(app, "/protected", token="t")
    assert code == 200
    assert jsonlib.loads(body) == {"ok": True}
