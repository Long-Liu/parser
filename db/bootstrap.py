import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from db.config import load_config
from db.connection import create_engine, create_sessionmaker
from db.schema import init_db, create_data_table
from db.seed import seed_defaults
from utils.config_loader import list_configs

logger = logging.getLogger("parser")


def register(app):
    @app.listener("before_server_start")
    async def startup(app):
        app.ctx.config = load_config()
        logger.info(f"env={os.getenv('APP_ENV', 'local')} debug={app.ctx.config.DEBUG}")

        engine = create_engine(app.ctx.config)
        app.ctx.engine = engine
        app.ctx.Session = create_sessionmaker(engine, AsyncSession)

        await init_db(engine)
        logger.info("db tables created")

        session = app.ctx.Session()
        try:
            await seed_defaults(session)
        finally:
            await session.close()
        logger.info("db seed done")

        for cfg in list_configs():
            await create_data_table(engine, cfg["template_id"], cfg.get("columns", []))
        logger.info(f"{len(list_configs())} data tables ready")

    @app.listener("after_server_stop")
    async def shutdown(app):
        if hasattr(app.ctx, "engine"):
            await app.ctx.engine.dispose()
        logger.info("db closed")
