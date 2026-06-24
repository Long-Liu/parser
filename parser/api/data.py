import json as _json
from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth, require_permission

bp = Blueprint("data", url_prefix="/api/data")


@bp.get("/<template_id>")
@require_auth
@require_permission("data:view")
async def get_data(request, template_id):
    pool = request.app.ctx.pool
    batch_id = request.args.get("batch_id")
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 200))
    offset = (page - 1) * size

    table_name = f"data_{template_id}"

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if batch_id:
                await cur.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE batch_id=%s",
                    (batch_id,),
                )
                count_row = await cur.fetchone()
                total = count_row[0] if count_row else 0

                await cur.execute(
                    f"SELECT * FROM {table_name} WHERE batch_id=%s LIMIT %s OFFSET %s",
                    (batch_id, size, offset),
                )
            else:
                await cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_row = await cur.fetchone()
                total = count_row[0] if count_row else 0

                await cur.execute(
                    f"SELECT * FROM {table_name} LIMIT %s OFFSET %s",
                    (size, offset),
                )

            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            data = []
            for row in rows:
                d = dict(zip(cols, row))
                if d.get("monthly_data") and isinstance(d["monthly_data"], str):
                    d["monthly_data"] = _json.loads(d["monthly_data"])
                if "created_at" in d and d["created_at"]:
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
