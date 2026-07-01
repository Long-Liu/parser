"""Application bootstrap: config → db.init → schema + seed + data tables."""

import logging
import os
from collections.abc import Callable

from contexts.shared.infrastructure.database.config import load_config
from contexts.shared.infrastructure.database.engine import init as db_init, close as db_close
from contexts.shared.infrastructure.database.schema import init_db, create_data_table
from contexts.shared.infrastructure.database.seed import seed_defaults

logger = logging.getLogger("parser")


def register(
    app,
    template_config_provider: Callable[[], list[dict]] | None = None,
    password_hasher: Callable[[str], str] | None = None,
):
    @app.listener("before_server_start")
    async def startup(app):
        app.ctx.config = load_config()
        logger.info("env=%s debug=%s", os.getenv("APP_ENV", "local"), app.ctx.config.DEBUG)

        await db_init(app.ctx.config)

        await init_db()
        logger.info("db tables created")

        if password_hasher is None:
            raise RuntimeError("password_hasher is required for database seed")
        await seed_defaults(password_hasher)
        logger.info("db seed done")

        configs = template_config_provider() if template_config_provider else []
        for cfg in configs:
            await create_data_table(cfg["template_id"])
        logger.info("%d data tables ready", len(configs))

    @app.listener("after_server_stop")
    async def shutdown(app):
        await db_close()
        logger.info("db closed")
