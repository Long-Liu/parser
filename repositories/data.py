"""Template data table CRUD — used by the data service layer."""

import json as _json

import sqlalchemy as sa

from db.connection import execute, fetch_val, fetch_all
from db.tables import data_table_for


class DataRepo:
    """CRUD for dynamic data_{template_id} tables — no fixed table attribute."""

    @staticmethod
    async def insert_rows(template_id: str, rows: list[dict]):
        """Insert extracted rows into data_{template_id}."""
        if not rows:
            return
        dtable = data_table_for(template_id)
        value_dicts = [
            {**{c: row.get(c) for c in row if c != "monthly_data"},
             "monthly_data": _json.dumps(row.get("monthly_data", {}), ensure_ascii=False)}
            for row in rows
        ]
        await execute(dtable.insert(), value_dicts)

    @staticmethod
    async def query(template_id: str, batch_id: int | None = None,
                    page: int = 1, size: int = 200) -> dict:
        """Paginated query of data_{template_id}."""
        dtable = data_table_for(template_id)
        offset = (page - 1) * size

        if batch_id:
            count_stmt = (sa.select(sa.func.count().label("cnt"))
                           .select_from(dtable)
                           .where(dtable.c.batch_id == batch_id))
            data_stmt = (dtable.select()
                          .where(dtable.c.batch_id == batch_id)
                          .limit(size).offset(offset))
        else:
            count_stmt = sa.select(sa.func.count().label("cnt")).select_from(dtable)
            data_stmt = dtable.select().limit(size).offset(offset)

        total = await fetch_val(count_stmt) or 0
        rows = await fetch_all(data_stmt)

        cols = list(rows[0].keys()) if rows else []
        data = []
        for row in rows:
            d = dict(row)
            if d.get("monthly_data") and isinstance(d["monthly_data"], str):
                d["monthly_data"] = _json.loads(d["monthly_data"])
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            data.append(d)

        return {"total": total, "page": page, "size": size, "rows": data, "columns": cols}
