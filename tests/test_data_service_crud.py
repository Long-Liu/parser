import pytest
from sqlalchemy.exc import IntegrityError

from repositories.data_repository import DataRepo
from services.data_service import (
    create_data_row,
    delete_data_row,
    get_data,
    get_data_row,
    update_data_row,
)
from services.errors_service import ConflictError, ServiceError


TEMPLATE_ID = "labor_cost"


def _patch_columns(monkeypatch):
    monkeypatch.setattr(
        DataRepo,
        "table_columns",
        lambda template_id: [
            "id",
            "batch_id",
            "hierarchy_code",
            "person_name",
            "monthly_data",
            "created_at",
        ],
    )


@pytest.mark.asyncio
async def test_get_data_rejects_unknown_template():
    with pytest.raises(ServiceError) as exc:
        await get_data("missing_template")

    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_get_data_row_returns_404_when_missing(monkeypatch):
    async def fake_get_by_id(template_id, row_id):
        return None

    monkeypatch.setattr(DataRepo, "get_by_id", fake_get_by_id)

    with pytest.raises(ServiceError) as exc:
        await get_data_row(TEMPLATE_ID, 1)

    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_create_data_row_requires_batch_id(monkeypatch):
    _patch_columns(monkeypatch)

    with pytest.raises(ServiceError) as exc:
        await create_data_row(TEMPLATE_ID, {"person_name": "Alice"})

    assert exc.value.http_status == 400
    assert str(exc.value) == "batch_id is required"


@pytest.mark.asyncio
async def test_create_data_row_rejects_unknown_fields(monkeypatch):
    _patch_columns(monkeypatch)

    with pytest.raises(ServiceError) as exc:
        await create_data_row(TEMPLATE_ID, {"batch_id": 1, "bad_field": "x"})

    assert exc.value.http_status == 400
    assert str(exc.value) == "unknown fields: bad_field"


@pytest.mark.asyncio
async def test_create_data_row_rejects_readonly_fields(monkeypatch):
    _patch_columns(monkeypatch)

    with pytest.raises(ServiceError) as exc:
        await create_data_row(TEMPLATE_ID, {"id": 1, "batch_id": 1})

    assert exc.value.http_status == 400
    assert str(exc.value) == "readonly fields: id"


@pytest.mark.asyncio
async def test_create_data_row_maps_integrity_error_to_conflict(monkeypatch):
    _patch_columns(monkeypatch)

    async def fake_insert_row(template_id, values):
        raise IntegrityError("statement", "params", "orig")

    monkeypatch.setattr(DataRepo, "insert_row", fake_insert_row)

    with pytest.raises(ConflictError):
        await create_data_row(TEMPLATE_ID, {"batch_id": 999})


@pytest.mark.asyncio
async def test_update_data_row_rejects_empty_payload(monkeypatch):
    _patch_columns(monkeypatch)

    async def fake_get_by_id(template_id, row_id):
        return {"id": row_id, "batch_id": 1}

    monkeypatch.setattr(DataRepo, "get_by_id", fake_get_by_id)

    with pytest.raises(ServiceError) as exc:
        await update_data_row(TEMPLATE_ID, 1, {})

    assert exc.value.http_status == 400
    assert str(exc.value) == "at least one writable field is required"


@pytest.mark.asyncio
async def test_update_data_row_returns_updated_row(monkeypatch):
    _patch_columns(monkeypatch)
    calls = {}

    async def fake_get_by_id(template_id, row_id):
        if calls.get("updated"):
            return {"id": row_id, "batch_id": 1, "person_name": "Bob"}
        return {"id": row_id, "batch_id": 1, "person_name": "Alice"}

    async def fake_update_by_id(template_id, row_id, values):
        calls["updated"] = values

    monkeypatch.setattr(DataRepo, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(DataRepo, "update_by_id", fake_update_by_id)

    row = await update_data_row(TEMPLATE_ID, 1, {"person_name": "Bob"})

    assert calls["updated"] == {"person_name": "Bob"}
    assert row["person_name"] == "Bob"


@pytest.mark.asyncio
async def test_delete_data_row_returns_404_when_missing(monkeypatch):
    async def fake_get_by_id(template_id, row_id):
        return None

    monkeypatch.setattr(DataRepo, "get_by_id", fake_get_by_id)

    with pytest.raises(ServiceError) as exc:
        await delete_data_row(TEMPLATE_ID, 1)

    assert exc.value.http_status == 404


def test_data_repo_serializes_monthly_data():
    assert DataRepo.serialize_value("monthly_data", {"2026-07": 10}) == '{"2026-07": 10}'
    assert DataRepo.serialize_value("person_name", "Alice") == "Alice"
