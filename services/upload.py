"""Upload service — file processing orchestration."""

import asyncio
import logging
import os
import uuid
from contextlib import closing
from datetime import datetime

import aiofiles
import openpyxl
from sanic.request import File

from core.pipeline import run_pipeline
from db.primitives import transactional
from repositories.batch import BatchRepo, LogRepo
from services.data import insert_rows
from utils.config_loader import match_template

logger = logging.getLogger("parser.upload")
UPLOAD_DIR = os.path.abspath(os.environ.get("UPLOAD_DIR", "uploads"))


def _determine_status(all_success: bool, any_success: bool) -> str:
    if not any_success:
        return "skipped"
    if all_success:
        return "success"
    return "partial"


def _make_batch_no() -> str:
    return f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


async def _process_sheet(ws, sheet_name: str, batch_id: int) -> dict:
    config = match_template(sheet_name)
    if not config:
        await LogRepo.insert(
            batch_id=batch_id, sheet_name=sheet_name, template_id=None,
            action="skipped",
        )
        return {"name": sheet_name, "template": None, "rows": 0, "status": "skipped"}

    result = await asyncio.to_thread(run_pipeline, ws, batch_id, config)

    await LogRepo.insert(
        batch_id=batch_id, sheet_name=sheet_name,
        template_id=result["template_id"], action="matched",
        total_rows=result["total_rows"], success_rows=result["success_rows"],
        error_rows=result["error_rows"],
    )

    if result["rows"]:
        tid = result.get("template_id")
        if tid:
            await insert_rows(tid, result["rows"])

    return {
        "name": sheet_name,
        "template": result["template_id"],
        "rows": result["success_rows"],
        "status": "success" if result["error_rows"] == 0 else "partial",
    }


@transactional
async def _process_workbook(wb, batch_no: str, project_id: int, ym: str,
                            user_id: int, file_name: str, file_size: int) -> dict:
    batch_id = await BatchRepo.insert(
        batch_no=batch_no, project_id=project_id, ym=ym,
        uploaded_by=user_id, file_name=file_name,
        file_size=file_size,
    )

    sheet_results = []
    all_success = True
    any_success = False

    for sheet_name in wb.sheetnames:
        r = await _process_sheet(wb[sheet_name], sheet_name, batch_id)
        sheet_results.append(r)
        if r["status"] != "success":
            all_success = False
        if r["rows"] > 0:
            any_success = True

    status = _determine_status(all_success, any_success)
    await BatchRepo.update(
        BatchRepo._t().c.id == batch_id, status=status
    )

    return {"batch_id": batch_id, "status": status, "sheets": sheet_results}


async def process_upload(file: File, project_id: int, ym: str, user_id: int) -> dict:
    """Process an uploaded Excel file. Returns {batch_id, batch_no, status, sheets}."""
    batch_no = _make_batch_no()

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(file.body)
    file_size = os.path.getsize(filepath)

    try:
        wb = await asyncio.to_thread(openpyxl.load_workbook, filepath, data_only=True)
        with closing(wb):
            processed = await _process_workbook(
                wb, batch_no, project_id, ym, user_id, file.name, file_size
            )
            batch_id = processed["batch_id"]
            status = processed["status"]
            sheet_results = processed["sheets"]

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("upload failed for batch %s", batch_no)
        batch_id = await BatchRepo.insert(
            batch_no=batch_no, project_id=project_id, ym=ym,
            uploaded_by=user_id, file_name=file.name,
            file_size=file_size, status="failed",
        )
        status = "failed"
        sheet_results = []
    finally:
        try:
            os.remove(filepath)
        except OSError:
            logger.debug("failed to remove temp file %s", filepath, exc_info=True)

    return {
        "batch_id": batch_id, "batch_no": batch_no,
        "status": status, "sheets": sheet_results,
    }
