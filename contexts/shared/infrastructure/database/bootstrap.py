from __future__ import annotations

# Application bootstrap: config → db.init → schema + seed + data tables.
import logging
from collections.abc import Callable

from contexts.alert.domain.repositories import AlertPushDispatcher
from contexts.shared.infrastructure.config import Settings
from contexts.shared.infrastructure.database.engine import close as db_close
from contexts.shared.infrastructure.database.engine import init as db_init
from contexts.shared.infrastructure.database.schema import create_data_table, migrate_db
from contexts.shared.infrastructure.database.seed import seed_defaults

logger = logging.getLogger("parser")


def register(
    app,
    settings: Settings,
    alert_dispatcher: AlertPushDispatcher,
    template_config_provider: Callable[[], list[dict]] | None = None,
    password_hasher: Callable[[str], str] | None = None,
):
    @app.listener("before_server_start")
    async def startup(app):
        logger.info("env=%s debug=%s", settings.app.env, settings.debug)

        await db_init(settings)

        await migrate_db(settings)
        logger.info("db migrations applied")

        if password_hasher is None:
            raise RuntimeError("password_hasher is required for database seed")
        await seed_defaults(password_hasher, settings)
        logger.info("db seed done")

        # Drain any stale alert outbox entries (context is active here)
        try:
            await alert_dispatcher.dispatch_pending()
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
