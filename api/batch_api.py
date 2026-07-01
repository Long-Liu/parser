from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from middleware.auth import require_auth, require_permission
from services.batch_service import list_batches, get_batch
from utils.validators import get_query_int

bp = Blueprint("batches", url_prefix="/api/batches")


@bp.get("/")
@require_auth
@require_permission("data:view")
@openapi.tag("Batches")
@openapi.summary("List upload batches")
async def get_batches(request):
    try:
        project_id = get_query_int(request.args, "project_id")
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    batches = await list_batches(project_id=project_id, ym=request.args.get("ym"))
    return json({"batches": batches})


@bp.get("/<batch_id:int>")
@require_auth
@openapi.tag("Batches")
@openapi.summary("Get batch detail with logs")
async def get_batch_detail(request, batch_id):
    batch = await get_batch(batch_id)
    if not batch:
        return json({"error": "not found"}, status=404)
    return json(batch)
