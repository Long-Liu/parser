from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth
from parser.models.batch import get_batch, list_batches, get_logs_by_batch

bp = Blueprint("batches", url_prefix="/api/batches")


@bp.get("/")
@require_auth
async def get_batches(request):
    pool = request.app.ctx.pool
    project_id = request.args.get("project_id")
    year_month = request.args.get("year_month")
    batches = await list_batches(pool, project_id=int(project_id) if project_id else None,
                                  year_month=year_month)
    return json({"batches": batches})


@bp.get("/<batch_id:int>")
@require_auth
async def get_batch_detail(request, batch_id):
    pool = request.app.ctx.pool
    batch = await get_batch(pool, batch_id)
    if not batch:
        return json({"error": "not found"}, status=404)
    logs = await get_logs_by_batch(pool, batch_id)
    batch["logs"] = logs
    return json(batch)
