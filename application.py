"""Sanic application factory and deployment entry point."""

import logging

from sanic import Sanic
from sanic_ext import Extend

from contexts.auth.infrastructure.seed import seed_defaults
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

    app = Sanic("excel_parser")
    app.ctx.settings = settings
    app.ctx.config = settings  # compatibility for existing extensions
    app.ctx.services = RequestServices(
        authorization=components.authorization_service,
        project_access=components.project_access_policy,
    )
    app.config.FALLBACK_ERROR_FORMAT = "json"
    app.config.API_TITLE = "Excel Parser API"
    app.config.API_VERSION = "1.0.0"
    app.config.API_DESCRIPTION = "建筑成本数据解析与查询服务"
    Extend(app)

    setup_logging(debug=settings.debug)
    register_logging(app)
    register_cors(app, settings)
    register_controllers(app, build_controllers(components))
    register_db(
        app,
        settings,
        components.alert_dispatcher,
        template_config_provider=YamlTemplateLoader().template_ids,
        seeder=lambda: seed_defaults(components.password_hasher.hash, settings),
    )
    app.blueprint(health_bp)

    @app.exception(DomainError)
    async def on_domain_error(request, exception: DomainError):
        return error_to_response(exception)

    @app.exception(Exception)
    async def on_unhandled_error(request, exception: Exception):
        _logger.exception("unhandled exception on %s %s", request.method, request.path)
        from sanic.response import json
        return json({"error": "internal server error"}, status=500)

    return app


# WSGI/ASGI and the existing ``python main.py`` entry points import this name.
app = create_app()
