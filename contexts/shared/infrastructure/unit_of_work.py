from __future__ import annotations

import contextvars
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_sessionmaker

_tx_session: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar(
    "uow_session", default=None
)


def current_session() -> AsyncSession | None:
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


async def _demo():
    uow = SqlAlchemyUnitOfWork()
    assert isinstance(uow, UnitOfWork)
    print("unit_of_work: OK")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
