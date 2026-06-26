"""Database connection — module-level engine, zero-param execute()."""

import asyncio
import functools
import logging

import aiomysql.sa as aiosa
import pymysql
import sqlalchemy as sa
from aiomysql.sa.result import ResultProxy
from sqlalchemy.dialects.mysql import pymysql as _mysql_dialect

from db.config import Config

# Fix aiomysql.sa + SQLAlchemy 2.0 incompatibility
_mysql_dialect.MySQLDialect_pymysql.case_sensitive = True

logger = logging.getLogger("parser.db")

_POOL_RECYCLE_SECONDS = 3600
_MAX_RETRY_ATTEMPTS = 3
_RETRY_DELAY = 0.3

_engine: aiosa.Engine | None = None


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, pymysql.OperationalError):
        code = exc.args[0] if exc.args else 0
        return code in (2003, 2006, 2013)
    return isinstance(exc, (TimeoutError, ConnectionResetError))


def with_retry(func):
    """Decorator: retry async function on transient DB errors (max 3 attempts)."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        last_exc = None
        for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not _is_transient_error(exc):
                    raise
                last_exc = exc
                if attempt < _MAX_RETRY_ATTEMPTS:
                    logger.warning("db retry %d/%d after: %s", attempt, _MAX_RETRY_ATTEMPTS, exc)
                    await asyncio.sleep(_RETRY_DELAY * attempt)
        raise last_exc  # type: ignore[misc]
    return wrapper


async def init(config: Config) -> None:
    """Call once at startup. Creates the engine and stores it at module level."""
    global _engine
    _engine = await aiosa.create_engine(  # type: ignore[no-any-return]
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME,
        charset="utf8mb4",
        minsize=config.DB_POOL_MIN_SIZE,
        maxsize=config.DB_POOL_SIZE,
        pool_recycle=_POOL_RECYCLE_SECONDS,
    )


async def close() -> None:
    """Call at shutdown. Disposes the engine."""
    global _engine
    if _engine:
        _engine.close()
        await _engine.wait_closed()
        _engine = None


async def execute(
    stmt: sa.ClauseElement | sa.TextClause | str,
    params: dict | list[dict] | None = None,
) -> ResultProxy:
    """Single statement with BEGIN/COMMIT/ROLLBACK. Returns ResultProxy.

    Usage:
        result = await execute(users.select().where(users.c.id == 1))
        row = await result.fetchone()
    """
    assert _engine is not None, "db.init() must be called before execute()"
    async with _engine.acquire() as conn:
        async with conn.begin():
            return await conn.execute(stmt, params if params is not None else {})


class Transaction:
    """Context manager for multiple statements in one transaction.

    Usage:
        async with Transaction() as conn:
            await conn.execute(users.insert().values(name="Alice"))
            await conn.execute(logs.insert().values(action="created"))
    """
    def __init__(self) -> None:
        self._conn: aiosa.SAConnection | None = None
        self._tx = None  # type: ignore[assignment]  # internal aiomysql context manager

    async def __aenter__(self) -> aiosa.SAConnection:
        assert _engine is not None, "db.init() must be called before Transaction()"
        self._conn = await _engine.acquire().__aenter__()
        self._tx = await self._conn.begin().__aenter__()
        assert self._conn is not None
        return self._conn

    async def __aexit__(self, *args) -> None:
        if self._tx:
            await self._tx.__aexit__(*args)
        if self._conn:
            await self._conn.__aexit__(*args)
