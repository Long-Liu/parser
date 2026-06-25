import json as _json
import os
import uuid
from datetime import datetime

import openpyxl
from sanic import Blueprint
from sanic.response import json

from core.pipeline import Pipeline
from middleware.auth import require_auth, require_permission
from repositories.batch import create_batch, update_batch_status, insert_log
from utils.config_loader import match_template

bp = Blueprint("upload", url_prefix="/api")

UPLOAD_DIR = "uploads"


def _determine_status(all_success: bool, any_success: bool) -> str:
    if all_success and any_success:
        return "success"
    elif any_success:
        return "partial"
    return "failed"


async def _process_sheet(pool, ws, sheet_name: str, batch_id: int) -> dict:
    """处理单个 sheet：匹配模板 → 解析 → 入库。返回结果摘要。"""
    config = match_template(sheet_name)
    if not config:
        await insert_log(pool, batch_id, sheet_name, None, "skipped")
        return {"name": sheet_name, "template": None, "rows": 0, "status": "skipped"}

    pipeline = Pipeline(config)
    result = pipeline.run(ws, batch_id)

    await insert_log(
        pool, batch_id, sheet_name, result["template_id"],
        "matched", result["total_rows"], result["success_rows"], result["error_rows"],
    )

    if result["rows"]:
        table_name = f"data_{result['template_id']}"
        await _insert_rows(pool, table_name, result["rows"])

    return {
        "name": sheet_name,
        "template": result["template_id"],
        "rows": result["success_rows"],
        "status": "success" if result["error_rows"] == 0 else "partial",
    }


async def _insert_rows(pool, table_name: str, rows: list[dict]):
    if not rows:
        return
    sample = rows[0]
    fixed_cols = [k for k in sample.keys() if k != "monthly_data"]

    placeholders = ", ".join(["%s"] * (len(fixed_cols) + 1))
    cols_str = ", ".join(fixed_cols + ["monthly_data"])

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for row in rows:
                values = [row.get(c) for c in fixed_cols] + [
                    _json.dumps(row.get("monthly_data", {}), ensure_ascii=False)
                ]
                sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})"
                await cur.execute(sql, values)


@bp.post("/upload")
@require_auth
@require_permission("data:upload")
async def upload(request):
    if "file" not in request.files:
        return json({"error": "no file"}, status=400)

    file = request.files.get("file")
    if isinstance(file, list):
        file = file[0]
    project_id = int(request.form.get("project_id", 0))
    ym = request.form.get("ym", datetime.now().strftime("%Y-%m"))
    batch_no = request.form.get(
        "batch_no", f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    )

    if project_id <= 0:
        return json({"error": "invalid project_id"}, status=400)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")
    with open(filepath, "wb") as f:
        f.write(file.body)

    pool = request.app.ctx.pool
    batch_id = await create_batch(
        pool, batch_no=batch_no, project_id=project_id, ym=ym,
        uploaded_by=request.ctx.user_id, file_name=file.name,
        file_size=os.path.getsize(filepath),
    )

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheet_results = []
        all_success = True
        any_success = False

        for sheet_name in wb.sheetnames:
            r = await _process_sheet(pool, wb[sheet_name], sheet_name, batch_id)
            sheet_results.append(r)
            if r["status"] == "partial":
                all_success = False
            if r["rows"] > 0:
                any_success = True

        status = _determine_status(all_success, any_success)
        await update_batch_status(pool, batch_id, status)

    except Exception as e:
        await update_batch_status(pool, batch_id, "failed")
        return json({
            "batch_id": batch_id, "batch_no": batch_no,
            "status": "failed", "error": str(e),
        }, status=500)

    return json({
        "batch_id": batch_id, "batch_no": batch_no,
        "status": status, "sheets": sheet_results,
    })