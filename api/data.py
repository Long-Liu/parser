from sqlalchemy import text
from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth, require_permission

bp = Blueprint("data", url_prefix="/api/data")


@bp.get("/<template_id>")
@require_auth
@require_permission("data:view")
async def get_data(request, template_id):
    session = request.app.ctx.Session()
    try:
        batch_id = request.args.get("batch_id")
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 200))
        offset = (page - 1) * size
        table_name = f"data_{template_id}"

        if batch_id:
            result = await session.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE batch_id=:bid"), {"bid": batch_id}
            )
            total = result.scalar()
            result = await session.execute(
                text(f"SELECT * FROM {table_name} WHERE batch_id=:bid LIMIT :lim OFFSET :off"),
                {"bid": batch_id, "lim": size, "off": offset},
            )
        else:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            total = result.scalar()
            result = await session.execute(
                text(f"SELECT * FROM {table_name} LIMIT :lim OFFSET :off"),
                {"lim": size, "off": offset},
            )

        rows = result.fetchall()
        cols = list(result.keys())
        import json as _json
        data = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get("monthly_data") and isinstance(d["monthly_data"], str):
                d["monthly_data"] = _json.loads(d["monthly_data"])
            if d.get("created_at") and d["created_at"]:
                d["created_at"] = str(d["created_at"])
            data.append(d)

        return json({"template_id": template_id, "total": total, "page": page, "size": size, "rows": data, "columns": cols})
    finally:
        await session.close()
