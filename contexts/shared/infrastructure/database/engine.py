from __future__ import annotations

# Async SQLAlchemy engine lifecycle.

import logging

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from contexts.shared.infrastructure.database.config import Config

logger = logging.getLogger("parser.db")

_POOL_RECYCLE_SECONDS = 3600

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


async def init(config: Config) -> None:
    """Create the module-level async engine."""
    global _engine, _sessionmaker
    if _engine is not None:
        await close()

    url = URL.create(
        "mysql+aiomysql",
        username=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        query={"charset": "utf8mb4"},
    )
    _engine = create_async_engine(
        url,
        pool_size=config.DB_POOL_SIZE,
        max_overflow=0,
        pool_recycle=_POOL_RECYCLE_SECONDS,
        pool_pre_ping=True,
    )
    _sessionmaker = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def close() -> None:
    """Dispose the module-level async engine."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("db.init() must be called first")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("db.init() must be called first")
    return _sessionmaker
