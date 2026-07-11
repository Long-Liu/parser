from __future__ import annotations

# Application bootstrap: config → db.init → schema + seed + data tables.

import logging
import os
from collections.abc import Callable

from contexts.shared.infrastructure.database.config import load_config
from contexts.shared.infrastructure.database.engine import init as db_init, close as db_close
from contexts.shared.infrastructure.database.schema import migrate_db, create_data_table
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
        # Wire the JWT secret into the container once at startup
        from contexts.container import container
        container.configure(app.ctx.config.SECRET_KEY)
        logger.info("env=%s debug=%s", os.getenv("APP_ENV", "local"), app.ctx.config.DEBUG)

        await db_init(app.ctx.config)

        await migrate_db(app.ctx.config)
        logger.info("db migrations applied")

        if password_hasher is None:
            raise RuntimeError("password_hasher is required for database seed")
        await seed_defaults(password_hasher)
        logger.info("db seed done")

        # Drain any stale alert outbox entries (context is active here)
        try:
            from contexts.alert.domain.repositories import AlertPushDispatcher
            from contexts.container import container
            await container.get(AlertPushDispatcher).dispatch_pending()
        except Exception:
            logger.debug("startup outbox drain skipped", exc_info=True)

        configs = template_config_provider() if template_config_provider else []
        for cfg in configs:
            await create_data_table(cfg["template_id"])
        logger.info("%d data tables ready", len(configs))

    @app.listener("after_server_stop")
    async def shutdown(app):
        await db_close()
        logger.info("db closed")
