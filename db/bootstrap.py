"""Application bootstrap: config → db.init → schema + seed + data tables."""

import logging
import os

from db.config import load_config
from db.connection import init as db_init, close as db_close
from db.schema import init_db, create_data_table
from db.seed import seed_defaults
from utils.config_loader import list_configs

logger = logging.getLogger("parser")


def register(app):
    @app.listener("before_server_start")
    async def startup(app):
        app.ctx.config = load_config()
        logger.info("env=%s debug=%s", os.getenv("APP_ENV", "local"), app.ctx.config.DEBUG)

        await db_init(app.ctx.config)

        await init_db()
        logger.info("db tables created")

        await seed_defaults()
        logger.info("db seed done")

        configs = list_configs()
        for cfg in configs:
            await create_data_table(cfg["template_id"])
        logger.info("%d data tables ready", len(configs))

    @app.listener("after_server_stop")
    async def shutdown(app):
        await db_close()
        logger.info("db closed")
