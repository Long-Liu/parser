from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps


class TransactionManager(ABC):
    @abstractmethod
    def transaction(self) -> AsyncIterator[None]: ...


class NoopTransactionManager(TransactionManager):
    @asynccontextmanager
    async def transaction(self):
        yield


_after_commit: ContextVar[list[Callable[[], Awaitable[None]]] | None] = ContextVar(
    "after_commit", default=None
)


class TransactionalService:
    """Base for services with explicitly injected transaction boundaries."""

    def __init__(self, transaction_manager: TransactionManager | None = None) -> None:
        self._transaction_manager = transaction_manager or NoopTransactionManager()

    @property
    def transaction_manager(self) -> TransactionManager:
        return self._transaction_manager


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
        if not args or not isinstance(args[0], TransactionalService):
            raise RuntimeError("@transactional requires a TransactionalService method")
        manager = args[0]._transaction_manager
        if _after_commit.get() is not None:
            return await function(*args, **kwargs)
        callbacks: list[Callable[[], Awaitable[None]]] = []
        token = _after_commit.set(callbacks)
        try:
            async with manager.transaction():
                result = await function(*args, **kwargs)
        finally:
            _after_commit.reset(token)
        for callback in callbacks:
            await callback()
        return result
    return wrapped
