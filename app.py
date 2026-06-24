from sanic import Sanic
from sanic.response import json
from parser.db.connection import init_pool, engine, SessionLocal
from parser.db.schema import init_db, create_data_table
from parser.utils.config_loader import list_configs

app = Sanic("excel_parser")


@app.listener("before_server_start")
async def setup_db(app):
    # SQLAlchemy engine + session factory
    await init_pool(app)

    # Create all fixed tables
    await init_db()

    # Seed roles/permissions/admin user
    from parser.db.seed import seed_defaults
    session = SessionLocal()
    try:
        await seed_defaults(session)
    finally:
        await session.close()

    # Create data tables from template configs
    configs = list_configs()
    for config in configs:
        await create_data_table(config["template_id"], config.get("columns", []))


@app.listener("after_server_stop")
async def close_db(app):
    if hasattr(app.ctx, "engine"):
        await app.ctx.engine.dispose()


@app.get("/health")
async def health(request):
    return json({"status": "ok"})


# Register blueprints
from parser.api.auth import bp as auth_bp
from parser.api.project import bp as project_bp
from parser.api.upload import bp as upload_bp
from parser.api.data import bp as data_bp
from parser.api.template import bp as template_bp
from parser.api.batch import bp as batch_bp

app.blueprint(auth_bp)
app.blueprint(project_bp)
app.blueprint(upload_bp)
app.blueprint(data_bp)
app.blueprint(template_bp)
app.blueprint(batch_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
