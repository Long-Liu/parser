import os, uuid, json as _json
from datetime import datetime
from sanic import Blueprint
from sanic.response import json
from sqlalchemy import text
from parser.middleware.auth import require_auth, require_permission
from parser.models.batch import create_batch, update_batch_status, insert_log
from parser.models.template import get_template_by_id
from parser.core.pipeline import Pipeline
from parser.utils.config_loader import match_template
import openpyxl

bp = Blueprint("upload", url_prefix="/api")
UPLOAD_DIR = "uploads"


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
    batch_no = request.form.get("batch_no", f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}")

    if project_id <= 0:
        return json({"error": "invalid project_id"}, status=400)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")
    with open(filepath, "wb") as f:
        f.write(file.body)
    file_size = os.path.getsize(filepath)

    session = request.app.ctx.Session()
    try:
        async with session.begin():
            batch_id = await create_batch(session, batch_no=batch_no, project_id=project_id,
                                           ym=ym, uploaded_by=request.ctx.user_id,
                                           file_name=file.name, file_size=file_size)

            wb = openpyxl.load_workbook(filepath, data_only=True)
            sheet_results = []
            all_success, any_success = True, False

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                config = match_template(sheet_name)

                if not config:
                    await insert_log(session, batch_id, sheet_name, None, "skipped")
                    sheet_results.append({"name": sheet_name, "template": None, "rows": 0, "status": "skipped"})
                    continue

                pipeline = Pipeline(config)
                result = pipeline.run(ws, batch_id)

                await insert_log(session, batch_id, sheet_name, result["template_id"],
                                 "matched", result["total_rows"], result["success_rows"],
                                 result["error_rows"])

                if result["rows"]:
                    table_name = f"data_{result['template_id']}"
                    await _insert_rows(session, table_name, result["rows"])

                sheet_results.append({
                    "name": sheet_name, "template": result["template_id"],
                    "rows": result["success_rows"],
                    "status": "success" if result["error_rows"] == 0 else "partial",
                })
                if result["error_rows"] > 0:
                    all_success = False
                if result["success_rows"] > 0:
                    any_success = True

            status = "success" if (all_success and any_success) else ("partial" if any_success else "failed")
            await update_batch_status(session, batch_id, status)

        return json({"batch_id": batch_id, "batch_no": batch_no, "status": status, "sheets": sheet_results})
    except Exception as e:
        return json({"batch_id": batch_id if 'batch_id' in dir() else 0, "batch_no": batch_no, "status": "failed", "error": str(e)}, status=500)
    finally:
        await session.close()


async def _insert_rows(session, table_name, rows):
    if not rows:
        return
    sample = rows[0]
    fixed_cols = [k for k in sample.keys() if k != "monthly_data"]
    cols_str = ", ".join(fixed_cols + ["monthly_data"])
    placeholders = ", ".join([f":{k}" for k in fixed_cols] + [":monthly_data"])
    for row in rows:
        vals = {k: row.get(k) for k in fixed_cols}
        vals["monthly_data"] = _json.dumps(row.get("monthly_data", {}), ensure_ascii=False)
        await session.execute(text(f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"), vals)
