"""Verify the imported Excel data: re-extract with the same pipeline and
compare every row/column against the database rows of the latest batch.

Usage: .venv\\Scripts\\python.exe scripts/verify_import.py
"""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from contexts.parsing.domain.cell_unmerger import CellUnmerger
from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.data_validator import DataValidator
from contexts.parsing.domain.header_flattener import HeaderFlattener
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.parsing.infrastructure.data_writer import _model_values
from contexts.parsing.infrastructure.workbook_reader import OpenPyxlWorkbookReader
from contexts.shared.infrastructure.config import load_settings
from contexts.shared.infrastructure.database.engine import close as db_close
from contexts.shared.infrastructure.database.engine import init as db_init
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
from contexts.template.infrastructure.repositories import YamlTemplateCatalog

EXCEL = Path("excel/01 电源A项目动态成本基础表-0714.xlsx")

# 旧 batch 78（同一文件）导入成功时的每 sheet 行数 —— 确定性基准。
EXPECTED_ROW_COUNTS = {
    "dynamic_indicator": 76,
    "labor_cost": 73,
    "social_insurance": 71,
    "site_management": 81,
    "machinery": 38,
    "bid_comparison": 6,
    "construction_dynamic": 17,
    "installation_dynamic": 26,
    "other_items": 14,
    "material_cost": 343,
    "budget_adjustment_summary": 68,
    "budget_adjustment_internal": 4,
    "budget_increase": 2,
    "budget_lease": 2,
    "settlement_output": 14,
}


async def main() -> None:
    settings = load_settings()
    await db_init(settings)

    # 最新成功批次
    from contexts.parsing.infrastructure.tables import UploadBatch

    batch = await UploadBatch.filter(status="success").order_by("-id").first()
    if batch is None:
        raise SystemExit("no successful batch found — run scripts/reimport_excel.py first")
    batch_id = batch.id
    print(f"verifying batch {batch_id} ({batch.batch_no}, ym={batch.ym})")

    catalog = YamlTemplateCatalog()
    unmerger = CellUnmerger()
    flattener = HeaderFlattener()
    stop_detector = StopDetector()
    extractor = DataRowExtractor(stop_detector)
    validator = DataValidator()

    workbook_sheets = await OpenPyxlWorkbookReader().read(str(EXCEL))
    total_ok = total_bad = 0
    for sheet in workbook_sheets:
        template = await catalog.find_matching(sheet.name)
        if template is None:
            print(f"[skip] {sheet.name!r}: no template match")
            continue
        if template.id is None:
            print(f"[error] {sheet.name!r}: template without id")
            continue
        template_id = template.id.value
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            print(f"[error] {sheet.name!r}: no model for template {template_id}")
            continue

        grid = unmerger.unmerge(sheet.grid, sheet.merged_ranges)
        flat_headers = flattener.flatten(grid, template.header_spec.header_rows)
        extracted = extractor.extract(grid, flat_headers, template)
        valid_rows, errors = validator.validate(extracted, template)

        db_rows = await model.filter(batch_id=batch_id).order_by("id")
        ok = True
        problems = []
        coerced_columns: set[str] = set()
        expected_count = EXPECTED_ROW_COUNTS.get(template_id)
        if len(valid_rows) != len(db_rows):
            ok = False
            problems.append(f"row count: excel={len(valid_rows)} db={len(db_rows)} expected={expected_count}")
        if expected_count is not None and len(valid_rows) != expected_count:
            ok = False
            problems.append(f"row count drift vs old batch: expected={expected_count}")
        if errors:
            ok = False
            problems.append(f"validation errors: {len(errors)} (first: {errors[0].row_index})")

        # 逐行逐列比对（列 = 模板 db_field + batch_id/hierarchy_code/monthly_data）
        for idx, (expected_row, db_row) in enumerate(zip(valid_rows, db_rows, strict=True)):
            expected: dict = {"batch_id": batch_id, **expected_row.fields}
            if expected_row.hierarchy_code:
                expected["hierarchy_code"] = expected_row.hierarchy_code
            if expected_row.monthly_data:
                expected["monthly_data"] = expected_row.monthly_data
            normalized = _model_values(model, expected)
            for col, value in normalized.items():
                actual = getattr(db_row, col)
                if not _values_equal(value, actual):
                    ok = False
                    problems.append(
                        f"row {idx} col {col}: excel={value!r} db={actual!r}"
                    )
                    break  # 每行只报第一个差异，避免刷屏
                elif _semantic_type(value) != _semantic_type(actual):
                    coerced_columns.add(col)

        if ok:
            total_ok += 1
            note = f" (类型强转列: {sorted(coerced_columns)})" if coerced_columns else ""
            print(
                f"[ok]   {sheet.name!r} -> {template_id}: {len(db_rows)} rows"
                f"{note}"
            )
        else:
            total_bad += 1
            print(f"[BAD]  {sheet.name!r} -> {template_id}:")
            for p in problems[:8]:
                print(f"        - {p}")

    print(f"\nresult: {total_ok} sheets ok, {total_bad} sheets bad (of {len(workbook_sheets)})")
    await db_close()


def _semantic_type(v):
    """语义类型：date 列存 date/datetime 视为同类；数值/字符串区分。"""
    if isinstance(v, (datetime, date)):
        return "date"
    if isinstance(v, (int, float, Decimal)):
        return "number"
    if isinstance(v, str):
        return "str"
    return type(v).__name__


def _values_equal(expected, actual) -> bool:
    """值比较；DB 列类型可能把数值/日期强制转成字符串（varchar 列），
    此时按字符串比值；dict/list 保持结构相等；date 列返回 date 而 Excel
    解析为 datetime，比较时取日期部分。"""
    if expected is None and actual is None:
        return True
    if isinstance(expected, (dict, list)) or isinstance(actual, (dict, list)):
        return expected == actual
    if isinstance(expected, datetime) and isinstance(actual, date) and not isinstance(actual, datetime):
        return expected.date() == actual
    if isinstance(actual, datetime) and isinstance(expected, date) and not isinstance(expected, datetime):
        return actual.date() == expected
    if type(expected) is type(actual):
        return expected == actual
    return str(expected) == str(actual)


if __name__ == "__main__":
    asyncio.run(main())
