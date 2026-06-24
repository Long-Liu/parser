import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "1234"),
    "db": os.getenv("DB_NAME", "excel_parser"),
}

URL = f"mysql+aiomysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['db']}?charset=utf8mb4"

engine = create_async_engine(URL, pool_size=5, max_overflow=10, echo=False)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """返回一个新的数据库会话"""
    return SessionLocal()


async def init_pool(app=None):
    """兼容旧接口，注册到 app.ctx"""
    if app:
        app.ctx.engine = engine
        app.ctx.Session = SessionLocal
