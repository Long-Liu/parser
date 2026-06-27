"""Parse pipeline: unmerge → flatten headers → extract → validate."""

from openpyxl.worksheet.worksheet import Worksheet

from core.cell_unmerger import unmerge
from core.data_extractor import extract_rows
from core.header_flattener import flatten_headers
from core.validator import validate


def run_pipeline(ws: Worksheet, batch_id: int, config: dict) -> dict:
    sheet_name = ws.title

    grid = unmerge(ws)
    header_rows = [r - 1 for r in config.get("headers", {}).get("rows", [])]
    flat_headers = flatten_headers(grid, header_rows)

    rows = extract_rows(grid, flat_headers, config)
    columns = config.get("columns", [])
    valid_rows, errors = validate(rows, columns)

    error_row_count = len({e["row_index"] for e in errors})

    for row in valid_rows:
        row["batch_id"] = batch_id

    return {
        "template_id": config.get("template_id"),
        "sheet_name": sheet_name,
        "total_rows": len(rows),
        "success_rows": len(rows) - error_row_count,
        "error_rows": error_row_count,
        "rows": valid_rows,
        "errors": errors,
    }
