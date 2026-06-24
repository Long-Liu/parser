import pytest
import os
from parser.core.pipeline import Pipeline
from parser.utils.config_loader import match_template
import openpyxl


def test_full_parse_with_real_excel():
    excel_path = "excel/xxx项目主体施工动态成本表-样式 - 副本.xlsx"
    if not os.path.exists(excel_path):
        pytest.skip("Excel file not found")

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    results = []
    skipped = 0

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        config = match_template(sheet_name)
        if config:
            pipeline = Pipeline(config)
            result = pipeline.run(ws, batch_id=0)
            results.append(result)
            print(f"\n  {result['sheet_name']}: {result['success_rows']} rows "
                  f"({result['error_rows']} errors) [template: {result['template_id']}]")
        else:
            skipped += 1
            print(f"\n  {sheet_name}: SKIPPED (no template match)")

    matched = len(results)
    print(f"\nMatched sheets: {matched}, Skipped: {skipped}")
    total_rows = sum(r["success_rows"] for r in results)
    print(f"Total data rows extracted: {total_rows}")

    assert matched > 0, "At least one sheet should match a template"
    assert total_rows > 0, "Should extract some data"
