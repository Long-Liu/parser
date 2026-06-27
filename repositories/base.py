"""Base repository — table-driven CRUD via classmethods."""

import sqlalchemy as sa

from db.connection import select_one, select_all, select_val, insert_row, exec_stmt


class BaseRepo:
    """Inherit and set `table` to get standard CRUD.

    Usage:
        class UserRepo(BaseRepo):
            table = users

        user = await UserRepo.get(users.c.id == 1)
        rows  = await UserRepo.list()
        rows  = await UserRepo.list(users.c.is_active.is_(True))
        n     = await UserRepo.insert(name="Alice")
        await UserRepo.update(users.c.id == 1, name="Bob")
        cnt   = await UserRepo.count()
    """

    table: sa.Table | None = None

    @classmethod
    def _t(cls) -> sa.Table:
        if cls.table is None:
            raise TypeError(f"{cls.__name__}.table is not set")
        return cls.table

    @classmethod
    async def get(cls, *where) -> dict | None:
        """Fetch one row matching *where conditions, or None."""
        stmt = cls._t().select()
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        return await select_one(stmt)

    @classmethod
    async def list(cls, *where, order_by=None, limit=None, offset=None) -> list[dict]:
        """Fetch all rows, optionally filtered/sorted/paginated."""
        stmt = cls._t().select()
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return await select_all(stmt)

    @classmethod
    async def insert(cls, **values) -> int:
        """Insert a row. Returns lastrowid."""
        return await insert_row(cls._t().insert().values(**values))

    @classmethod
    async def insert_ignore(cls, **values) -> int:
        """Insert a row with INSERT IGNORE. Returns lastrowid (0 if skipped)."""
        return await insert_row(cls._t().insert().prefix_with("IGNORE").values(**values))

    @classmethod
    async def update(cls, *where, **values):
        """Update rows matching *where conditions."""
        stmt = cls._t().update()
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        await exec_stmt(stmt.values(**values))

    @classmethod
    async def count(cls, *where) -> int:
        """Count rows, optionally filtered."""
        stmt = sa.select(sa.func.count()).select_from(cls._t())
        if where:
            stmt = stmt.where(sa.and_(*where) if len(where) > 1 else where[0])
        return (await select_val(stmt)) or 0
