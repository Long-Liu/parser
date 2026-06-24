import os
from sanic import Sanic
from sanic.response import json

app = Sanic("excel_parser")


@app.listener("before_server_start")
async def setup_db(app):
    # 根据环境变量加载配置（默认 local）
    from config import load_config
    app.ctx.config = load_config()

    # 用配置创建引擎
    from db.connection import create_engine, create_sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession
    engine = create_engine(app.ctx.config)
    app.ctx.engine = engine
    app.ctx.Session = create_sessionmaker(engine, AsyncSession)

    # Fixed tables
    from db.schema import init_db
    await init_db()

    # Seed
    from db.seed import seed_defaults
    session = app.ctx.Session()
    try:
        await seed_defaults(session)
    finally:
        await session.close()

    # Dynamic data tables from YAML configs
    from db.schema import create_data_table
    from utils.config_loader import list_configs
    for cfg in list_configs():
        await create_data_table(cfg["template_id"], cfg.get("columns", []))


@app.listener("after_server_stop")
async def close_db(app):
    if hasattr(app.ctx, "engine"):
        await app.ctx.engine.dispose()


@app.get("/health")
async def health(request):
    return json({"status": "ok", "env": os.getenv("APP_ENV", "local")})


from api.auth import bp as auth_bp
from api.project import bp as project_bp
from api.upload import bp as upload_bp
from api.data import bp as data_bp
from api.template import bp as template_bp
from api.batch import bp as batch_bp

app.blueprint(auth_bp)
app.blueprint(project_bp)
app.blueprint(upload_bp)
app.blueprint(data_bp)
app.blueprint(template_bp)
app.blueprint(batch_bp)
