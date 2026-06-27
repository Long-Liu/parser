"""Data service — query and insert for template data tables."""

from db.tables import TEMPLATE_DATA_TABLES
from repositories.data import DataRepo


async def get_data(template_id: str, batch_id: int | None = None,
                   page: int = 1, size: int = 200) -> dict:
    if template_id not in TEMPLATE_DATA_TABLES:
        raise ValueError("template not found")
    return await DataRepo.query(template_id, batch_id=batch_id, page=page, size=size)


async def insert_rows(template_id: str, rows: list[dict]):
    await DataRepo.insert_rows(template_id, rows)
