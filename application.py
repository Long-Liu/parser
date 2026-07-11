"""Sanic application assembly and configuration."""

import logging
import asyncio

from sanic import Sanic
from sanic_ext import Extend

# ── import controllers so @rest_controller decorators fire ───────────────────
import contexts.analytics.interface.analytics_controller  # noqa: F401
import contexts.alert.interface.alert_controller  # noqa: F401
import contexts.auth.interface.auth_controller  # noqa: F401
import contexts.auth.interface.role_controller  # noqa: F401
import contexts.auth.interface.user_controller  # noqa: F401
import contexts.data.interface.data_controller  # noqa: F401
import contexts.parsing.interface.batch_controller  # noqa: F401
import contexts.parsing.interface.upload_controller  # noqa: F401
import contexts.project.interface.project_controller  # noqa: F401
import contexts.template.interface.template_controller  # noqa: F401
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.container import container
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.infrastructure.database.bootstrap import register as register_db
from contexts.shared.infrastructure.database.config import load_config
from contexts.shared.infrastructure.logging import setup as setup_logging
from contexts.shared.interface.base_controller import error_to_response
from contexts.shared.interface.health_controller import bp as health_bp
from contexts.shared.interface.middleware.cors import register as register_cors
from contexts.shared.interface.middleware.logging import register as register_logging
from contexts.shared.interface.rest_controller import register_all
from contexts.template.infrastructure.config_loader import (
    list_configs as list_template_configs,
)
from contexts.alert.domain.repositories import AlertPushDispatcher

_logger = logging.getLogger("sanic.error")

app = Sanic("excel_parser")
app.config.FALLBACK_ERROR_FORMAT = "json"

app.config.API_TITLE = "Excel Parser API"
app.config.API_VERSION = "1.0.0"
app.config.API_DESCRIPTION = "建筑成本数据解析与查询服务"
Extend(app)

setup_logging()
register_logging(app)
register_cors(app)
register_db(
    app,
    template_config_provider=list_template_configs,
    password_hasher=BCryptPasswordHasher().hash,
)

# ── global error handlers — no try/except needed in any controller ────────────
@app.exception(DomainError)
async def on_domain_error(request, exception: DomainError):
    return error_to_response(exception)


@app.exception(Exception)
async def on_unhandled_error(request, exception: Exception):
    _logger.exception("unhandled exception on %s %s", request.method, request.path)
    from sanic.response import json

    return json({"error": "internal server error"}, status=500)


# ── mount all @rest_controller blueprints ────────────────────────────────────
container.configure(load_config().SECRET_KEY)
app.blueprint(health_bp)
register_all(app, container)


async def _alert_outbox_worker(app):
    while True:
        try:
            await container.get(AlertPushDispatcher).dispatch_pending()
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.exception("alert outbox dispatch failed")
        await asyncio.sleep(5)


@app.after_server_start
async def start_alert_outbox_worker(app):
    app.ctx.alert_outbox_task = app.add_task(_alert_outbox_worker(app))


@app.before_server_stop
async def stop_alert_outbox_worker(app):
    task = getattr(app.ctx, "alert_outbox_task", None)
    if task:
        task.cancel()
