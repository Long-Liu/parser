"""Async ORM transaction context helpers."""

import contextvars
import functools

from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_sessionmaker

_tx_session: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar(
    "tx_session", default=None
)


def current_session() -> AsyncSession | None:
    """Return the active transaction session for this task, if any."""
    return _tx_session.get()


def model_to_dict(obj) -> dict:
    """Convert a mapped ORM instance to a plain dict."""
    table = getattr(obj, "__table__", None)
    if table is None:
        return dict(obj)
    return {col.name: getattr(obj, col.name) for col in table.columns}


class Transaction:
    """Context manager for multi-statement async ORM transactions."""

    def __init__(self) -> None:
        self._ctx = None
        self._session: AsyncSession | None = None
        self._token: contextvars.Token | None = None
        self._owner = False

    async def __aenter__(self) -> "Transaction":
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


def transactional(func):
    """Decorator: run an async function inside a shared transaction."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with Transaction():
            return await func(*args, **kwargs)
    return wrapper
