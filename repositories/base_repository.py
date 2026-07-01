"""Base repository — ORM-driven CRUD via classmethods."""

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.primitives import current_session, model_to_dict


class BaseRepo:
    """Inherit and set `model` to get standard CRUD.

    Usage:
        class UserRepo(BaseRepo):
            model = User

        user = await UserRepo.get(users.c.id == 1)
        rows  = await UserRepo.list()
        rows  = await UserRepo.list(users.c.is_active.is_(True))
        n     = await UserRepo.insert(name="Alice")
        await UserRepo.update(users.c.id == 1, name="Bob")
        cnt   = await UserRepo.count()
    """

    model = None

    @classmethod
    def _model(cls):
        if cls.model is None:
            raise TypeError(f"{cls.__name__}.model is not set")
        return cls.model

    @classmethod
    def _t(cls) -> sa.Table:
        return cls._model().__table__

    @classmethod
    def _insert_ignore_stmt(cls, **values):
        stmt = sa.insert(cls._t())
        stmt = stmt.prefix_with("IGNORE")
        return stmt.values(**values)

    @classmethod
    async def _read(cls, stmt):
        session = current_session()
        if session is not None:
            return await session.execute(stmt)
        async with get_sessionmaker()() as session:
            return await session.execute(stmt)

    @classmethod
    async def _write(cls, stmt, params=None):
        session = current_session()
        if session is not None:
            return await session.execute(stmt, params if params is not None else {})
        async with get_sessionmaker().begin() as session:
            return await session.execute(stmt, params if params is not None else {})

    @classmethod
    async def get(cls, *where) -> dict | None:
        """Fetch one row matching *where conditions, or None."""
        stmt = sa.select(cls._model())
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        result = await cls._read(stmt)
        row = result.scalars().first()
        return model_to_dict(row) if row is not None else None

    @classmethod
    async def list(cls, *where, order_by=None, limit=None, offset=None) -> list[dict]:
        """Fetch all rows, optionally filtered/sorted/paginated."""
        stmt = sa.select(cls._model())
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await cls._read(stmt)
        return [model_to_dict(row) for row in result.scalars().all()]

    @classmethod
    async def insert(cls, **values) -> int:
        """Insert a row. Returns lastrowid."""
        obj = cls._model()(**values)
        session = current_session()
        if session is not None:
            session.add(obj)
            await session.flush()
            return getattr(obj, "id", 0) or 0
        async with get_sessionmaker().begin() as session:
            session.add(obj)
            await session.flush()
            return getattr(obj, "id", 0) or 0

    @classmethod
    async def insert_ignore(cls, **values) -> int:
        """Insert a row with MySQL INSERT IGNORE. Returns lastrowid (0 if skipped)."""
        stmt = cls._insert_ignore_stmt(**values)
        result = await cls._write(stmt)
        return result.lastrowid or 0

    @classmethod
    async def update(cls, *where, **values):
        """Update rows matching *where conditions."""
        stmt = sa.update(cls._t())
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        await cls._write(stmt.values(**values))

    @classmethod
    async def delete(cls, *where):
        """Delete rows matching *where conditions."""
        stmt = sa.delete(cls._t())
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        await cls._write(stmt)

    @classmethod
    async def count(cls, *where) -> int:
        """Count rows, optionally filtered."""
        stmt = sa.select(sa.func.count()).select_from(cls._t())
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        result = await cls._read(stmt)
        return result.scalar() or 0
