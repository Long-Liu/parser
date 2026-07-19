"""Integration tests: run the real parsing pipeline over the shipped workbooks.

Uses the project's own domain pipeline (unmerge -> flatten -> extract ->
validate) with YamlTemplateLoader configs against the two real Excel files
under excel/ (the old样式 workbook is git-tracked; the 0714 workbook is a
local fixture that is not committed). Guards the template adaptations made
for the 电源A dynamic-cost workbook format:

- every expected sheet matches a template and yields non-zero valid rows
- no validation errors on the new workbook
- key fields are actually populated (not just header-matched on paper)
- stop rules terminate extraction (no 65k-row runaway on 表5, 总计 cut on 表9,
  合计 cut on 表10/表10.1/表10.2/表10.3)
- retired sheets (毛利/表1-1/表9-1/表9-2/表9-3) are skipped on the old workbook
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contexts.parsing.domain.cell_unmerger import CellUnmerger
from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.data_validator import DataValidator
from contexts.parsing.domain.header_flattener import HeaderFlattener
from contexts.parsing.infrastructure.workbook_reader import OpenPyxlWorkbookReader
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader

EXCEL_DIR = Path(__file__).resolve().parent.parent / "excel"
NEW_WORKBOOK = EXCEL_DIR / "01 电源A项目动态成本基础表-0714.xlsx"
OLD_WORKBOOK = EXCEL_DIR / "xxx项目主体施工动态成本表-样式 - 副本.xlsx"

# template_id -> (a field that must be filled in at least one row)
EXPECTED_NEW = {
    "dynamic_indicator": "item_name",
    "labor_cost": "department",
    "social_insurance": "department",
    "site_management": "fee_name",
    "machinery": "planned_period",
    "bid_comparison": "item_name",
    "construction_dynamic": "project_name",
    "installation_dynamic": "project_name",
    "other_items": "item_name",
    "material_cost": "budget_category",
    "budget_adjustment_summary": "item_name",
    "budget_adjustment_internal": "request_no",
    "budget_increase": "increase_project",
    "budget_lease": "budget_subject",
    "settlement_output": "indicator_name",
}

# Exact data-row counts verified against the 0714 workbook; total rows
# (表10 项目成本合计, 表10.1/10.2/10.3 合计) must never leak into data rows.
EXPECTED_NEW_ROW_COUNTS = {
    "budget_adjustment_summary": 67,
    "budget_adjustment_internal": 3,
    "budget_increase": 3,
    "budget_lease": 1,
    "settlement_output": 14,
}

# Sheets that existed in the old workbook but lost their templates with the
# format change; they must now be skipped instead of parsed.
RETIRED_TEMPLATES = (
    "gross_profit", "labor_cost_summary", "concrete_ledger",
    "rebar_ledger", "installation_material",
)


async def _run_pipeline(path: Path):
    """template_id -> (valid_rows, errors) for every matched sheet."""
    templates = YamlTemplateLoader().load_all()
    sheets = await OpenPyxlWorkbookReader().read(str(path))
    unmerger, flattener = CellUnmerger(), HeaderFlattener()
    extractor, validator = DataRowExtractor(), DataValidator()
    results = {}
    for sheet in sheets:
        template = next((t for t in templates if t.matches_sheet(sheet.name)), None)
        if template is None:
            continue
        grid = unmerger.unmerge(sheet.grid, sheet.merged_ranges)
        flat = flattener.flatten(grid, template.header_spec.header_rows)
        rows = extractor.extract(grid, flat, template)
        valid, errors = validator.validate(rows, template)
        results[template.id.value] = (valid, errors)
    return results


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_all_expected_sheets_extract():
    results = await _run_pipeline(NEW_WORKBOOK)
    missing = set(EXPECTED_NEW) - set(results)
    assert not missing, f"templates with no matching sheet: {missing}"
    for template_id, key_field in EXPECTED_NEW.items():
        valid, errors = results[template_id]
        assert not errors, f"{template_id}: validation errors: {errors[:3]}"
        assert len(valid) > 0, f"{template_id}: 0 valid rows"
        filled = sum(1 for r in valid if r.fields.get(key_field) not in (None, ""))
        assert filled > 0, f"{template_id}: key field {key_field} never filled"


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_budget_and_settlement_sheets_exact_rows():
    results = await _run_pipeline(NEW_WORKBOOK)
    for template_id, expected in EXPECTED_NEW_ROW_COUNTS.items():
        valid, errors = results[template_id]
        assert not errors, f"{template_id}: validation errors: {errors[:3]}"
        assert len(valid) == expected, (
            f"{template_id}: {len(valid)} rows, expected {expected}"
        )
    # the 项目成本合计 grand-total row must be cut by the stop rule
    summary_rows, _ = results["budget_adjustment_summary"]
    assert all(
        not str(r.fields.get("item_name") or "").startswith("项目成本合计")
        for r in summary_rows
    )


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_stop_rules_terminate():
    results = await _run_pipeline(NEW_WORKBOOK)
    # 表5 has ~65k formatted rows; consecutive_empty_rows must cut it to the
    # real data (a handful of 标段 rows).
    bid_rows, _ = results["bid_comparison"]
    assert len(bid_rows) < 100
    # 表9 must stop before the trailing 总计 row.
    material_rows, _ = results["material_cost"]
    assert 300 < len(material_rows) < 345
    assert all(
        not str(r.fields.get("budget_category") or "").startswith("总计")
        for r in material_rows
    )


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_key_amount_fields():
    results = await _run_pipeline(NEW_WORKBOOK)

    indicator, _ = results["dynamic_indicator"]
    assert any(r.fields.get("indicator_ex_tax") for r in indicator)

    construction, _ = results["construction_dynamic"]
    assert any(r.fields.get("quota_code") for r in construction)
    assert any(r.fields.get("contract_total_price") for r in construction)

    installation, _ = results["installation_dynamic"]
    assert any(r.fields.get("contract_installation") for r in installation)

    other, _ = results["other_items"]
    assert any(r.fields.get("cost_amount") for r in other)

    material, _ = results["material_cost"]
    assert any(r.fields.get("indicator_total") for r in material)
    assert any(r.fields.get("actual_unpaid_total") for r in material)


@pytest.mark.skipif(not OLD_WORKBOOK.exists(), reason="old workbook not present")
async def test_old_workbook_still_parses():
    """Backward-compat smoke check on the legacy workbook."""
    results = await _run_pipeline(OLD_WORKBOOK)
    for template_id in ("dynamic_indicator", "bid_comparison", "other_items",
                        "material_cost", "installation_dynamic"):
        valid, _ = results[template_id]
        assert len(valid) > 0, f"{template_id}: 0 valid rows on old workbook"
    # the 表5 runaway must be fixed for the old workbook too
    assert len(results["bid_comparison"][0]) < 100


@pytest.mark.skipif(not OLD_WORKBOOK.exists(), reason="old workbook not present")
async def test_old_workbook_retired_sheets_are_skipped():
    """毛利/表1-1/表9-1/表9-2/表9-3 lost their templates with the format
    change; on the old workbook they must now be skipped, not parsed."""
    results = await _run_pipeline(OLD_WORKBOOK)
    for template_id in RETIRED_TEMPLATES:
        assert template_id not in results, (
            f"{template_id} unexpectedly matched a sheet on the old workbook"
        )
