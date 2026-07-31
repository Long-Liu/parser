"""Sanic application factory and deployment entry point."""

import logging
from typing import Any, cast

from sanic import Sanic
from sanic.exceptions import SanicException
from sanic.response import json
from sanic_ext import Extend

from contexts.auth.infrastructure.seed import seed_defaults
from contexts.auth.infrastructure.token_revocation_repository import (
    TortoiseTokenRevocationRepository,
)
from contexts.auth.interface.request_services import RequestServices
from contexts.container import build_container, build_controllers
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.infrastructure.config import Settings, load_settings
from contexts.shared.infrastructure.database.bootstrap import register as register_db
from contexts.shared.infrastructure.logging import setup as setup_logging
from contexts.shared.interface.base_controller import error_to_response
from contexts.shared.interface.controller_registration import register_controllers
from contexts.shared.interface.health_controller import bp as health_bp
from contexts.shared.interface.middleware.cors import register as register_cors
from contexts.shared.interface.middleware.logging import register as register_logging
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader

_logger = logging.getLogger("sanic.error")


def create_app(settings: Settings | None = None) -> Sanic:
    """Create a fully composed, independently testable application instance."""
    settings = settings or load_settings()
    components = build_container(settings)

    sanic_app = Sanic("excel_parser")
    sanic_app.ctx.settings = settings
    sanic_app.ctx.config = settings  # compatibility for existing extensions
    sanic_app.ctx.services = RequestServices(
        authorization=components.authorization_service,
        project_access=components.project_access_policy,
    )
    sanic_app.config.FALLBACK_ERROR_FORMAT = "json"
    sanic_app.config.API_TITLE = "Excel Parser API"
    sanic_app.config.API_VERSION = "1.0.0"
    sanic_app.config.API_DESCRIPTION = "建筑成本数据解析与查询服务"
    # Swagger supports interactive parameter entry and requests; ReDoc is
    # read-only, so use Swagger for the main /docs entry point.
    sanic_app.config.OAS_UI_DEFAULT = "swagger"
    Extend(sanic_app)
    openapi: Any = getattr(sanic_app.ext, "openapi", None)
    if openapi is not None:
        openapi.add_security_scheme(
            "bearerAuth",
            "http",
            scheme="bearer",
            bearer_format="JWT",
            description="在 Authorization 请求头中填写 Bearer JWT 访问令牌",
        )

    setup_logging(debug=settings.debug)
    register_logging(sanic_app)
    register_cors(sanic_app, settings)
    register_controllers(sanic_app, build_controllers(components))
    register_db(
        sanic_app,
        settings,
        components.alert_dispatcher,
        template_config_provider=YamlTemplateLoader().template_ids,
        seeder=lambda: seed_defaults(components.password_hasher.hash, cast(Settings, settings)),
        token_purge=TortoiseTokenRevocationRepository(),
    )
    sanic_app.blueprint(health_bp)

    @sanic_app.exception(DomainError)
    async def on_domain_error(_request, exception: DomainError):
        return error_to_response(exception)

    @sanic_app.exception(SanicException)
    async def on_sanic_error(_request, exception: SanicException):
        # Preserve framework HTTP errors such as 404. Without this handler the
        # broad Exception handler below turns an ordinary missing route into a
        # logged 500 response.
        return json(
            {"error": str(exception)},
            status=getattr(exception, "status_code", 500),
        )

    @sanic_app.exception(Exception)
    async def on_unhandled_error(request, _exception: Exception):
        _logger.exception("unhandled exception on %s %s", request.method, request.path)
        return json({"error": "internal server error"}, status=500)

    return sanic_app


# WSGI/ASGI and the existing ``python main.py`` entry points import this name.
app = create_app()
