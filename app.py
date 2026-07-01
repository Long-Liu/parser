"""Sanic application entry point."""

from sanic import Sanic
from sanic_ext import Extend

from api.auth_api import bp as auth_bp
from api.batch_api import bp as batch_bp
from api.data_api import bp as data_bp
from api.health_api import bp as health_bp
from api.project_api import bp as project_bp
from api.template_api import bp as template_bp
from api.upload_api import bp as upload_bp

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

for bp in [health_bp, auth_bp, project_bp, upload_bp, data_bp, template_bp, batch_bp]:
    app.blueprint(bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, single_process=True)
