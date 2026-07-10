"""Sanic application assembly and configuration."""

from sanic import Sanic
from sanic_ext import Extend

from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
# DDD context blueprints
from contexts.auth.interface.auth_controller import bp as auth_ddd_bp
from contexts.auth.interface.role_controller import bp as role_bp
from contexts.data.interface.data_controller import bp as data_ddd_bp
from contexts.parsing.interface.batch_controller import bp as batch_bp
from contexts.parsing.interface.upload_controller import bp as upload_ddd_bp
from contexts.project.interface.project_controller import bp as project_ddd_bp
from contexts.shared.infrastructure.database.bootstrap import register as register_db
from contexts.shared.infrastructure.logging import setup as setup_logging
from contexts.shared.interface.health_controller import bp as health_bp
from contexts.shared.interface.middleware.cors import register as register_cors
from contexts.shared.interface.middleware.logging import register as register_logging
from contexts.template.infrastructure.config_loader import list_configs as list_template_configs
from contexts.template.interface.template_controller import bp as template_ddd_bp

app = Sanic("excel_parser")
app.config.FALLBACK_ERROR_FORMAT = "json"

# OpenAPI (Swagger) — docs at /docs, spec at /openapi.json
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

for bp in [health_bp, batch_bp,
            auth_ddd_bp, role_bp, project_ddd_bp, upload_ddd_bp,
            data_ddd_bp, template_ddd_bp]:
    app.blueprint(bp)
