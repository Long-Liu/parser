"""Database connection — typed CRUD primitives with implicit-transaction support."""

import contextvars
import functools
import logging
import warnings

# aiomysql emits MySQL warnings via Python's warnings module on
# IF NOT EXISTS / INSERT IGNORE duplicates — suppress them
warnings.filterwarnings("ignore", module="aiomysql")

import aiomysql.sa as aiosa
import sqlalchemy as sa
from aiomysql.sa.result import ResultProxy
from sqlalchemy.dialects.mysql import pymysql as _mysql_dialect

from db.config import Config

# Fix aiomysql.sa + SQLAlchemy 2.0 incompatibility
_mysql_dialect.MySQLDialect_pymysql.case_sensitive = True

logger = logging.getLogger("parser.db")

_POOL_RECYCLE_SECONDS = 3600

_engine: aiosa.Engine | None = None

# Tracks the active Transaction's connection per async task.
_tx_conn: contextvars.ContextVar[aiosa.SAConnection | None] = contextvars.ContextVar(
    "tx_conn", default=None
)


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
        minsize=1,  # ponytail: per-pool tuning when needed
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


# ── internal ─────────────────────────────────────────────────────────────────

async def _run(
    stmt: sa.ClauseElement | sa.TextClause | str,
    params: dict | list[dict] | None = None,
) -> ResultProxy:
    """Route to tx connection or acquire new, execute, return ResultProxy."""
    assert _engine is not None, "db.init() must be called first"
    conn = _tx_conn.get()
    if conn is not None:
        return await conn.execute(stmt, params if params is not None else {})
    async with _engine.acquire() as conn:
        async with conn.begin():
            return await conn.execute(stmt, params if params is not None else {})


# ── typed primitives ─────────────────────────────────────────────────────────

async def select_one(
    stmt: sa.ClauseElement | sa.TextClause,
    params: dict | None = None,
) -> dict | None:
    """SELECT → first row as dict, or None."""
    r = await _run(stmt, params)
    row = await r.fetchone()
    return dict(row) if row else None


async def select_all(
    stmt: sa.ClauseElement | sa.TextClause,
    params: dict | None = None,
) -> list[dict]:
    """SELECT → all rows as list[dict]."""
    r = await _run(stmt, params)
    return [dict(row) for row in await r.fetchall()]


async def select_val(
    stmt: sa.ClauseElement | sa.TextClause,
    params: dict | None = None,
):
    """SELECT → first column of first row (e.g. COUNT)."""
    r = await _run(stmt, params)
    row = await r.fetchone()
    return row[0] if row else None


async def insert_row(
    stmt: sa.ClauseElement,
    values: dict | list[dict] | None = None,
) -> int:
    """INSERT → lastrowid."""
    r = await _run(stmt, values)
    return r.lastrowid


async def exec_stmt(
    stmt: sa.ClauseElement | sa.TextClause,
    params: dict | None = None,
):
    """UPDATE / DELETE / INSERT...SELECT — no return value."""
    await _run(stmt, params)


async def exec_ddl(
    stmt: sa.ClauseElement | sa.TextClause | str,
):
    """CREATE TABLE / DDL — no return value."""
    await _run(stmt)


# ── transaction ──────────────────────────────────────────────────────────────

class _Transaction:
    """Context manager for multi-statement transactions.

    All primitives inside the block automatically share this connection.

    Usage:
        async with _Transaction():
            await UserRepo.insert(username="alice", ...)
            await RoleRepo.insert_ignore(code="admin", ...)
    """

    def __init__(self) -> None:
        self._conn: aiosa.SAConnection | None = None
        self._tx = None
        self._token: contextvars.Token | None = None

    async def __aenter__(self) -> "_Transaction":
        assert _engine is not None, "db.init() must be called first"
        self._conn = await _engine.acquire().__aenter__()
        self._tx = await self._conn.begin().__aenter__()
        self._token = _tx_conn.set(self._conn)
        return self

    async def __aexit__(self, *args) -> None:
        if self._token is not None:
            _tx_conn.reset(self._token)
        if self._tx:
            await self._tx.__aexit__(*args)
        if self._conn:
            await self._conn.__aexit__(*args)


def transactional(func):
    """Decorator: wrap an async function in a Transaction block.

    Usage:
        @transactional
        async def register_user(username, password, ...):
            uid = await UserRepo.insert(...)
            await UserRoleRepo.grant(uid, "admin")
            return uid, role_code
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with _Transaction():
            return await func(*args, **kwargs)
    return wrapper
