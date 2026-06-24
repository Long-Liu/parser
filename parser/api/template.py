from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth, require_permission
from parser.models.template import get_active_templates, register_template
from parser.utils.config_loader import load_config

bp = Blueprint("templates", url_prefix="/api/templates")


@bp.get("/")
@require_auth
async def get_templates(request):
    pool = request.app.ctx.pool
    templates = await get_active_templates(pool)
    return json({"templates": templates})


@bp.post("/")
@require_auth
@require_permission("template:manage")
async def post_template(request):
    data = request.json
    template_id = data["template_id"]
    config_yaml = data["config_yaml"]
    description = data.get("description", "")
    data_table = f"data_{template_id}"

    pool = request.app.ctx.pool
    tid = await register_template(pool, template_id, description, config_yaml, data_table)

    config = load_config(template_id)
    columns_sql = _build_create_table_sql(template_id, config)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(columns_sql)

    return json({"id": tid, "table": data_table}, status=201)


def _build_create_table_sql(template_id, config):
    cols = [
        "id INT AUTO_INCREMENT PRIMARY KEY",
        "batch_id INT NOT NULL",
        "hierarchy_code VARCHAR(50)",
    ]
    for col_def in config.get("columns", []):
        col_sql = f"{col_def['db_field']} {col_def.get('type', 'varchar(255)')}"
        cols.append(col_sql)
    cols.append("monthly_data JSON")
    cols.append("created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    cols.append("FOREIGN KEY (batch_id) REFERENCES upload_batches(id)")
    cols.append("INDEX idx_batch (batch_id)")
    cols.append("INDEX idx_hierarchy (hierarchy_code)")

    return f"CREATE TABLE IF NOT EXISTS data_{template_id} ({', '.join(cols)})"
