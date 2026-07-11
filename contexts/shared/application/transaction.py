from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import wraps
from contextvars import ContextVar
from collections.abc import Awaitable


class TransactionManager(ABC):
    @abstractmethod
    def transaction(self) -> AsyncIterator[None]: ...


class NoopTransactionManager(TransactionManager):
    @asynccontextmanager
    async def transaction(self):
        yield


_manager: TransactionManager = NoopTransactionManager()
_after_commit: ContextVar[list[Callable[[], Awaitable[None]]] | None] = ContextVar(
    "after_commit", default=None
)


def configure_transaction_manager(manager: TransactionManager) -> None:
    global _manager
    _manager = manager


def get_transaction_manager() -> TransactionManager:
    return _manager


def defer_after_commit(callback: Callable[[], Awaitable[None]]) -> bool:
    callbacks = _after_commit.get()
    if callbacks is None:
        return False
    callbacks.append(callback)
    return True


def transactional(function: Callable):
    """Application transaction boundary independent of the selected ORM."""
    @wraps(function)
    async def wrapped(*args, **kwargs):
        if _after_commit.get() is not None:
            return await function(*args, **kwargs)
        callbacks: list[Callable[[], Awaitable[None]]] = []
        token = _after_commit.set(callbacks)
        try:
            async with _manager.transaction():
                result = await function(*args, **kwargs)
        finally:
            _after_commit.reset(token)
        for callback in callbacks:
            await callback()
        return result
    return wrapped
