from sanic import Blueprint
from sanic.response import json
from parser.middleware.auth import require_auth
from parser.models.batch import get_batch, list_batches, get_logs_by_batch

bp = Blueprint("batches", url_prefix="/api/batches")


def _batch_to_dict(b):
    return {"id": b.id, "batch_no": b.batch_no, "project_id": b.project_id, "ym": b.ym,
            "uploaded_by": b.uploaded_by, "file_name": b.file_name, "file_size": b.file_size,
            "status": b.status, "created_at": str(b.created_at) if b.created_at else None}


@bp.get("/")
@require_auth
async def get_batches(request):
    session = request.app.ctx.Session()
    try:
        project_id = request.args.get("project_id")
        ym = request.args.get("ym")
        batches = await list_batches(session, project_id=int(project_id) if project_id else None, ym=ym)
        return json({"batches": [_batch_to_dict(b) for b in batches]})
    finally:
        await session.close()


@bp.get("/<batch_id:int>")
@require_auth
async def get_batch_detail(request, batch_id):
    session = request.app.ctx.Session()
    try:
        batch = await get_batch(session, batch_id)
        if not batch:
            return json({"error": "not found"}, status=404)
        logs = await get_logs_by_batch(session, batch_id)
        result = _batch_to_dict(batch)
        result["logs"] = [{"id": l.id, "sheet_name": l.sheet_name, "template_id": l.template_id,
                            "action": l.action, "total_rows": l.total_rows,
                            "success_rows": l.success_rows, "error_rows": l.error_rows} for l in logs]
        return json(result)
    finally:
        await session.close()
