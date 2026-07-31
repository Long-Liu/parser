from __future__ import annotations

# Application bootstrap: config → db.init → schema + seed + data tables.
# The seed step is injected as a callable by the composition root so this
# shared module stays free of any business-context imports.
import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Protocol

from contexts.shared.infrastructure.config import Settings
from contexts.shared.infrastructure.database.engine import close as db_close
from contexts.shared.infrastructure.database.engine import init as db_init
from contexts.shared.infrastructure.database.schema import (
    migrate_db,
    validate_data_table,
)

logger = logging.getLogger("parser")

# How often the alert outbox is swept for failed messages awaiting retry.
OUTBOX_RETRY_INTERVAL_SECONDS = 30

# How often expired JWT-blacklist rows are purged. The request path only
# SELECTs; the DELETE moved here to avoid per-request write amplification.
TOKEN_PURGE_INTERVAL_SECONDS = 60


class AlertOutboxDispatcher(Protocol):
    """Structural port for the alert outbox dispatcher.

    Declared locally so the shared context never imports from the alert
    context (the concrete implementation is TortoiseAlertOutboxDispatcher).
    """

    async def dispatch_pending(self) -> None: ...


class TokenPurge(Protocol):
    """Structural port for the revoked-token cleanup task.

    Declared locally so the shared context never imports from the auth
    context (the concrete implementation is TortoiseTokenRevocationRepository).
    """

    async def purge_expired(self) -> int: ...


def register(
    app,
    settings: Settings,
    alert_dispatcher: AlertOutboxDispatcher,
    template_config_provider: Callable[[], list[str]] | None = None,
    seeder: Callable[[], Awaitable[None]] | None = None,
    token_purge: TokenPurge | None = None,
):
    @app.listener("before_server_start")
    async def startup(_sanic_app):
        logger.info("env=%s debug=%s", settings.app.env, settings.debug)

        await db_init(settings)

        await migrate_db(settings)
        logger.info("db migrations applied")

        if seeder is None:
            raise RuntimeError("seeder is required for database bootstrap")
        await seeder()
        logger.info("db seed done")

        # Drain any stale alert outbox entries (context is active here)
        # noinspection PyBroadException
        try:
            await alert_dispatcher.dispatch_pending()
        except Exception:
            logger.debug("startup outbox drain skipped", exc_info=True)

        template_ids = template_config_provider() if template_config_provider else []
        for template_id in template_ids:
            await validate_data_table(template_id)
        logger.info("%d data tables ready", len(template_ids))

    @app.listener("after_server_start")
    async def start_background_tasks(sanic_app):
        async def _retry_loop():
            while True:
                await asyncio.sleep(OUTBOX_RETRY_INTERVAL_SECONDS)
                # noinspection PyBroadException
                try:
                    await alert_dispatcher.dispatch_pending()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("periodic alert outbox dispatch failed")

        sanic_app.ctx.alert_outbox_retry_task = asyncio.create_task(_retry_loop())
        logger.info(
            "alert outbox retry scheduled every %ds",
            OUTBOX_RETRY_INTERVAL_SECONDS,
        )

        async def _purge_loop(purge: TokenPurge) -> None:
            while True:
                await asyncio.sleep(TOKEN_PURGE_INTERVAL_SECONDS)
                # noinspection PyBroadException
                try:
                    await purge.purge_expired()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("periodic revoked-token purge failed")

        if token_purge is not None:
            sanic_app.ctx.token_purge_task = asyncio.create_task(_purge_loop(token_purge))
            logger.info(
                "revoked-token purge scheduled every %ds",
                TOKEN_PURGE_INTERVAL_SECONDS,
            )

    @app.listener("after_server_stop")
    async def shutdown(sanic_app):
        task: asyncio.Task | None = getattr(sanic_app.ctx, "alert_outbox_retry_task", None)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            sanic_app.ctx.alert_outbox_retry_task = None
        purge_task: asyncio.Task | None = getattr(sanic_app.ctx, "token_purge_task", None)
        if purge_task is not None:
            purge_task.cancel()
            with suppress(asyncio.CancelledError):
                await purge_task
            sanic_app.ctx.token_purge_task = None
        await db_close()
        logger.info("db closed")
