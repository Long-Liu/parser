"""Unit of Work — transaction boundary for DDD aggregate persistence.

Provides:
- SqlAlchemyUnitOfWork: explicit commit/rollback context manager
- Transaction: alias for SqlAlchemyUnitOfWork (backward compat)
- transactional: decorator wrapping an async function in a Transaction
- current_session: return the active async session for this task, if any
"""

from __future__ import annotations

import contextvars
import functools
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_sessionmaker

_tx_session: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar(
    "uow_session", default=None
)


def current_session() -> AsyncSession | None:
    """Return the active transaction session for this task, if any."""
    return _tx_session.get()


class UnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork": ...

    @abstractmethod
    async def __aexit__(self, *args) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork(UnitOfWork):
    """UoW backed by a single SQLAlchemy async session.

    Supports nesting: if entered inside an existing session, it reuses it
    without beginning a new transaction.
    """

    def __init__(self) -> None:
        self._ctx = None
        self._session: AsyncSession | None = None
        self._token: contextvars.Token | None = None
        self._owner = False

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UoW not entered")
        return self._session

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        existing = current_session()
        if existing is not None:
            self._session = existing
            return self

        self._ctx = get_sessionmaker().begin()
        self._session = await self._ctx.__aenter__()
        self._token = _tx_session.set(self._session)
        self._owner = True
        return self

    async def __aexit__(self, *args) -> None:
        if self._owner and self._token is not None:
            _tx_session.reset(self._token)
        if self._owner and self._ctx is not None:
            await self._ctx.__aexit__(*args)

    async def commit(self) -> None:
        if self._session is not None:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()


# ponytail: alias for backward compat — legacy code expects "Transaction"
Transaction = SqlAlchemyUnitOfWork


def transactional(func):
    """Decorator: run an async function inside a shared Transaction."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with SqlAlchemyUnitOfWork():
            return await func(*args, **kwargs)

    return wrapper
