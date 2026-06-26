from sanic import Blueprint
from sanic.response import json

from middleware.auth import require_auth, require_permission
from repositories.batch import get_batch, list_batches, get_logs_by_batch

bp = Blueprint("batches", url_prefix="/api/batches")


def _parse_int_optional(value, name: str):
    """Safely parse an optional integer query parameter."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be an integer") from None


@bp.get("/")
@require_auth
@require_permission("data:view")
async def get_batches(request):
    project_id = request.args.get("project_id")
    ym = request.args.get("ym")
    try:
        parsed_pid = _parse_int_optional(project_id, "project_id")
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    batches = await list_batches(project_id=parsed_pid, ym=ym)
    return json({"batches": batches})


@bp.get("/<batch_id:int>")
@require_auth
async def get_batch_detail(request, batch_id):
    batch = await get_batch(batch_id)
    if not batch:
        return json({"error": "not found"}, status=404)
    logs = await get_logs_by_batch(batch_id)
    batch["logs"] = logs
    return json(batch)
