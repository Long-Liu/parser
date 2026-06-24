from sanic import Sanic
from sanic.response import json

app = Sanic("excel_parser")


@app.listener("before_server_start")
async def setup_db(app):
    from parser.db.connection import get_pool
    from parser.db.schema import init_db
    from parser.db.seed import seed_defaults

    pool = await get_pool()
    await init_db(pool)
    await seed_defaults(pool)
    await _create_template_tables(pool)
    app.ctx.pool = pool


async def _create_template_tables(pool):
    from parser.utils.config_loader import list_configs
    configs = list_configs()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for config in configs:
                tid = config["template_id"]
                cols = [
                    "id INT AUTO_INCREMENT PRIMARY KEY",
                    "batch_id INT NOT NULL",
                    "hierarchy_code VARCHAR(50)",
                ]
                for col_def in config.get("columns", []):
                    col_sql = f"`{col_def['db_field']}` {col_def.get('type', 'varchar(255)')}"
                    cols.append(col_sql)
                cols.append("monthly_data JSON")
                cols.append("created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                cols.append("INDEX idx_batch (batch_id)")
                cols.append("INDEX idx_hierarchy (hierarchy_code)")
                sql = f"CREATE TABLE IF NOT EXISTS data_{tid} ({', '.join(cols)})"
                await cur.execute(sql)


@app.listener("after_server_stop")
async def close_db(app):
    if hasattr(app.ctx, "pool"):
        app.ctx.pool.close()
        await app.ctx.pool.wait_closed()


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
