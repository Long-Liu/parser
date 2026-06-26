import json as _json

import sqlalchemy as sa
from sanic import Blueprint
from sanic.response import json

from db.connection import execute
from db.tables import data_table_for
from middleware.auth import require_auth, require_permission
from utils.config_loader import load_config
from utils.validators import is_valid_template_id

bp = Blueprint("data", url_prefix="/api/data")


@bp.get("/<template_id>")
@require_auth
@require_permission("data:view")
async def get_data(request, template_id):
    if not is_valid_template_id(template_id):
        return json({"error": "invalid template_id"}, status=400)

    batch_id = request.args.get("batch_id")

    try:
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 200))
    except (ValueError, TypeError):
        return json({"error": "page and size must be integers"}, status=400)
    if page < 1 or size < 1 or size > 1000:
        return json({"error": "page >= 1, 1 <= size <= 1000"}, status=400)

    offset = (page - 1) * size
    config = load_config(template_id)
    dtable = data_table_for(template_id, config.get("columns", []))

    if batch_id:
        count_result = await execute(
            sa.select(sa.func.count().label("cnt"))
            .select_from(dtable)
            .where(dtable.c.batch_id == batch_id))
        total = (await count_result.fetchone())["cnt"]

        result = await execute(
            dtable.select()
            .where(dtable.c.batch_id == batch_id)
            .limit(size).offset(offset))
    else:
        count_result = await execute(
            sa.select(sa.func.count().label("cnt")).select_from(dtable))
        total = (await count_result.fetchone())["cnt"]

        result = await execute(
            dtable.select().limit(size).offset(offset))

    rows = await result.fetchall()
    cols = list(rows[0].keys()) if rows else []
    data = []
    for row in rows:
        d = dict(row)
        if d.get("monthly_data") and isinstance(d["monthly_data"], str):
            d["monthly_data"] = _json.loads(d["monthly_data"])
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        data.append(d)

    return json({
        "template_id": template_id,
        "total": total,
        "page": page,
        "size": size,
        "rows": data,
        "columns": cols,
    })
