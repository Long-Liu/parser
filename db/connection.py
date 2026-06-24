from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


def create_engine(config):
    return create_async_engine(
        config.DB_URL,
        pool_size=config.DB_POOL_SIZE,
        max_overflow=10,
        echo=config.DEBUG,
    )


def create_sessionmaker(engine, async_session_class):
    return async_sessionmaker(engine, class_=async_session_class, expire_on_commit=False)
