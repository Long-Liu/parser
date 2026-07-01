"""Data service — query and insert for template data tables."""

from sqlalchemy.exc import IntegrityError

from db.tables import TEMPLATE_DATA_TABLES
from repositories.data_repository import DataRepo
from services.errors_service import ConflictError, ServiceError


READONLY_FIELDS = frozenset({"id", "created_at"})


async def get_data(template_id: str, batch_id: int | None = None,
                   page: int = 1, size: int = 200) -> dict:
    _ensure_template_exists(template_id)
    return await DataRepo.query(template_id, batch_id=batch_id, page=page, size=size)


async def insert_rows(template_id: str, rows: list[dict]):
    await DataRepo.insert_rows(template_id, rows)


async def get_data_row(template_id: str, row_id: int) -> dict:
    _ensure_template_exists(template_id)
    row = await DataRepo.get_by_id(template_id, row_id)
    if row is None:
        raise ServiceError("not found", http_status=404)
    return row


async def create_data_row(template_id: str, data: dict) -> dict:
    _ensure_template_exists(template_id)
    values = _validate_payload(template_id, data, require_batch_id=True)
    try:
        row_id = await DataRepo.insert_row(template_id, values)
    except IntegrityError:
        raise ConflictError("data row conflicts with existing constraints") from None
    return await get_data_row(template_id, row_id)


async def update_data_row(template_id: str, row_id: int, data: dict) -> dict:
    _ensure_template_exists(template_id)
    existing = await DataRepo.get_by_id(template_id, row_id)
    if existing is None:
        raise ServiceError("not found", http_status=404)

    values = _validate_payload(template_id, data, require_batch_id=False)
    if not values:
        raise ServiceError("at least one writable field is required", http_status=400)

    try:
        await DataRepo.update_by_id(template_id, row_id, values)
    except IntegrityError:
        raise ConflictError("data row conflicts with existing constraints") from None
    return await get_data_row(template_id, row_id)


async def delete_data_row(template_id: str, row_id: int) -> None:
    _ensure_template_exists(template_id)
    existing = await DataRepo.get_by_id(template_id, row_id)
    if existing is None:
        raise ServiceError("not found", http_status=404)
    await DataRepo.delete_by_id(template_id, row_id)


def _ensure_template_exists(template_id: str) -> None:
    if template_id not in TEMPLATE_DATA_TABLES:
        raise ServiceError("template not found", http_status=404)


def _validate_payload(template_id: str, data: dict, *, require_batch_id: bool) -> dict:
    if not isinstance(data, dict):
        raise ServiceError("request body must be JSON object", http_status=400)

    columns = set(DataRepo.table_columns(template_id))
    writable_columns = columns - READONLY_FIELDS

    readonly_fields = sorted(READONLY_FIELDS & set(data))
    if readonly_fields:
        raise ServiceError(
            f"readonly fields: {', '.join(readonly_fields)}",
            http_status=400,
        )

    unknown_fields = sorted(set(data) - columns)
    if unknown_fields:
        raise ServiceError(
            f"unknown fields: {', '.join(unknown_fields)}",
            http_status=400,
        )

    values = {key: value for key, value in data.items() if key in writable_columns}
    if require_batch_id and values.get("batch_id") is None:
        raise ServiceError("batch_id is required", http_status=400)
    return values
