"""Template data table CRUD — used by the data service layer."""

import json as _json

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.models import data_model_for
from db.primitives import current_session, model_to_dict


class DataRepo:
    """CRUD for dynamic data_{template_id} tables — no fixed table attribute."""

    @staticmethod
    async def _read(stmt):
        session = current_session()
        if session is not None:
            return await session.execute(stmt)
        async with get_sessionmaker()() as session:
            return await session.execute(stmt)

    @staticmethod
    async def _write(stmt, params=None):
        session = current_session()
        if session is not None:
            return await session.execute(stmt, params if params is not None else {})
        async with get_sessionmaker().begin() as session:
            return await session.execute(stmt, params if params is not None else {})

    @staticmethod
    def table_columns(template_id: str) -> list[str]:
        """Return column names for data_{template_id}."""
        model = data_model_for(template_id)
        return [column.name for column in model.__table__.columns]

    @staticmethod
    def serialize_value(column: str, value):
        if column == "monthly_data" and value is not None and not isinstance(value, str):
            return _json.dumps(value, ensure_ascii=False)
        return value

    @staticmethod
    def _deserialize_row(row) -> dict:
        d = model_to_dict(row)
        if d.get("monthly_data") and isinstance(d["monthly_data"], str):
            d["monthly_data"] = _json.loads(d["monthly_data"])
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        return d

    @staticmethod
    async def insert_rows(template_id: str, rows: list[dict]):
        """Insert extracted rows into data_{template_id}."""
        if not rows:
            return
        model = data_model_for(template_id)
        values = []
        for row in rows:
            values.append({
                **{c: row.get(c) for c in row if c != "monthly_data"},
                "monthly_data": _json.dumps(row.get("monthly_data", {}), ensure_ascii=False),
            })
        fields = sorted({key for row in values for key in row})
        values = [{field: row.get(field) for field in fields} for row in values]
        stmt = sa.insert(model.__table__).values({field: sa.bindparam(field) for field in fields})
        await DataRepo._write(stmt, values)

    @staticmethod
    async def get_by_id(template_id: str, row_id: int) -> dict | None:
        """Fetch one row by id from data_{template_id}."""
        model = data_model_for(template_id)
        stmt = sa.select(model).where(model.__table__.c.id == row_id)
        result = await DataRepo._read(stmt)
        row = result.scalars().first()
        return DataRepo._deserialize_row(row) if row is not None else None

    @staticmethod
    async def insert_row(template_id: str, values: dict) -> int:
        """Insert one row into data_{template_id}. Returns inserted id."""
        model = data_model_for(template_id)
        obj = model(**{
            key: DataRepo.serialize_value(key, value)
            for key, value in values.items()
        })
        session = current_session()
        if session is not None:
            session.add(obj)
            await session.flush()
            return getattr(obj, "id", 0) or 0
        async with get_sessionmaker().begin() as session:
            session.add(obj)
            await session.flush()
            return getattr(obj, "id", 0) or 0

    @staticmethod
    async def update_by_id(template_id: str, row_id: int, values: dict) -> None:
        """Update one row by id in data_{template_id}."""
        model = data_model_for(template_id)
        stmt = (
            sa.update(model.__table__)
            .where(model.__table__.c.id == row_id)
            .values(**{
                key: DataRepo.serialize_value(key, value)
                for key, value in values.items()
            })
        )
        await DataRepo._write(stmt)

    @staticmethod
    async def delete_by_id(template_id: str, row_id: int) -> None:
        """Delete one row by id from data_{template_id}."""
        model = data_model_for(template_id)
        stmt = sa.delete(model.__table__).where(model.__table__.c.id == row_id)
        await DataRepo._write(stmt)

    @staticmethod
    async def delete(template_id: str, batch_id: int | None = None):
        """Delete rows from data_{template_id}, optionally scoped to a batch."""
        model = data_model_for(template_id)
        stmt = sa.delete(model)
        if batch_id is not None:
            stmt = stmt.where(model.__table__.c.batch_id == batch_id)
        await DataRepo._write(stmt)

    @staticmethod
    async def query(template_id: str, batch_id: int | None = None,
                    page: int = 1, size: int = 200) -> dict:
        """Paginated query of data_{template_id}."""
        model = data_model_for(template_id)
        offset = (page - 1) * size

        if batch_id:
            count_stmt = (sa.select(sa.func.count().label("cnt"))
                           .select_from(model.__table__)
                           .where(model.__table__.c.batch_id == batch_id))
            data_stmt = (sa.select(model)
                          .where(model.__table__.c.batch_id == batch_id)
                          .limit(size).offset(offset))
        else:
            count_stmt = sa.select(sa.func.count().label("cnt")).select_from(model.__table__)
            data_stmt = sa.select(model).limit(size).offset(offset)

        total = (await DataRepo._read(count_stmt)).scalar() or 0
        result = await DataRepo._read(data_stmt)
        rows = result.scalars().all()

        cols = list(rows[0].__table__.columns.keys()) if rows else []
        data = []
        for row in rows:
            data.append(DataRepo._deserialize_row(row))

        return {"total": total, "page": page, "size": size, "rows": data, "columns": cols}
