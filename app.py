"""Sanic application entry point."""

from sanic import Sanic

from api.auth import bp as auth_bp
from api.batch import bp as batch_bp
from api.data import bp as data_bp
# Routes
from api.health import bp as health_bp
from api.project import bp as project_bp
from api.template import bp as template_bp
from api.upload import bp as upload_bp
# Logging
from core.logging import setup as setup_logging
# Database
from db.bootstrap import register as register_db
from middleware.cors import register as register_cors
# Middleware
from middleware.logging import register as register_logging

app = Sanic("excel_parser")
app.config.FALLBACK_ERROR_FORMAT = "json"

setup_logging()

register_logging(app)
register_cors(app)
register_db(app)

for bp in [health_bp, auth_bp, project_bp, upload_bp, data_bp, template_bp, batch_bp]:
    app.blueprint(bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, single_process=True)
