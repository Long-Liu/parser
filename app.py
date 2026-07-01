"""Sanic application entry point."""

from sanic import Sanic
from sanic_ext import Extend

from api.health_api import bp as health_bp
from contexts.parsing.interface.batch_controller import bp as batch_bp

# DDD context blueprints
from contexts.auth.interface.auth_controller import bp as auth_ddd_bp
from contexts.project.interface.project_controller import bp as project_ddd_bp
from contexts.template.interface.template_controller import bp as template_ddd_bp
from contexts.parsing.interface.upload_controller import bp as upload_ddd_bp
from contexts.data.interface.data_controller import bp as data_ddd_bp

from core.logging import setup as setup_logging

from db.bootstrap import register as register_db

from middleware.cors import register as register_cors
from middleware.logging import register as register_logging

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
register_db(app)

for bp in [health_bp, batch_bp,
            auth_ddd_bp, project_ddd_bp, upload_ddd_bp,
            data_ddd_bp, template_ddd_bp]:
    app.blueprint(bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, single_process=True)
