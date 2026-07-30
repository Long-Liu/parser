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

# Exact data-row counts verified against the 0714 workbook, including each
# sheet's final 合计/总计/小计 row.
EXPECTED_NEW_ROW_COUNTS = {
    "dynamic_indicator": 76,
    "construction_dynamic": 17,
    "installation_dynamic": 26,
    "machinery": 38,
    "bid_comparison": 6,
    "other_items": 14,
    "material_cost": 343,
    "budget_adjustment_summary": 68,
    "budget_adjustment_internal": 4,
    "budget_increase": 2,
    "budget_lease": 2,
    "settlement_output": 14,
}

# Sheets that existed in the old workbook but lost their templates with the
# format change; they must now be skipped instead of parsed.
RETIRED_TEMPLATES = (
    "gross_profit",
    "labor_cost_summary",
    "concrete_ledger",
    "rebar_ledger",
    "installation_material",
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
async def test_dynamic_indicator_extracts_all_ui_detail_columns():
    results = await _run_pipeline(NEW_WORKBOOK)
    rows, errors = results["dynamic_indicator"]
    assert not errors
    first = rows[0].fields
    for field in (
        "display_level",
        "linked_sheet",
        "adjusted_tax_rate",
        "adjusted_tax",
        "adjustment",
        "current_budget",
        "incurred_cost",
        "forecast_ex_tax",
        "forecast_tax_rate",
        "forecast_tax",
        "forecast_with_tax",
        "forecast_remark",
    ):
        assert field in first, field
    assert first["display_level"] == "一级显示"
    assert first["forecast_with_tax"] is not None


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_budget_and_settlement_sheets_exact_rows():
    results = await _run_pipeline(NEW_WORKBOOK)
    for template_id, expected in EXPECTED_NEW_ROW_COUNTS.items():
        valid, errors = results[template_id]
        assert not errors, f"{template_id}: validation errors: {errors[:3]}"
        assert len(valid) == expected, f"{template_id}: {len(valid)} rows, expected {expected}"
    # The 项目成本合计 grand-total row must be retained as the final row.
    summary_rows, _ = results["budget_adjustment_summary"]
    assert str(summary_rows[-1].fields["item_name"]).startswith("项目成本合计")


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_stop_rules_terminate():
    results = await _run_pipeline(NEW_WORKBOOK)
    # 表5 has ~65k formatted rows; consecutive_empty_rows must cut it to the
    # real data (a handful of 标段 rows).
    bid_rows, _ = results["bid_comparison"]
    assert len(bid_rows) < 100
    # 表9 must retain the trailing 总计 row and stop there.
    material_rows, _ = results["material_cost"]
    assert 300 < len(material_rows) < 345
    assert material_rows[-1].fields["budget_category"] == "总计"


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_stop_rules_match_real_tail_rows():
    results = await _run_pipeline(NEW_WORKBOOK)

    dynamic, _ = results["dynamic_indicator"]
    assert dynamic[-1].row_index == 81

    construction, _ = results["construction_dynamic"]
    assert construction[-1].row_index == 21
    assert construction[-1].fields["project_name"] == "合计"
    assert construction[-1].fields["bill_qty"] is None

    installation, _ = results["installation_dynamic"]
    assert installation[-1].row_index == 30

    internal, _ = results["budget_adjustment_internal"]
    assert internal[-1].row_index == 8
    assert internal[-1].fields["project_name"].replace(" ", "") == "合计"

    lease, _ = results["budget_lease"]
    assert lease[-1].row_index == 8
    assert lease[-1].fields["request_name"].replace(" ", "") == "合计"


@pytest.mark.skipif(not NEW_WORKBOOK.exists(), reason="new workbook not present")
async def test_new_workbook_key_amount_fields():
    results = await _run_pipeline(NEW_WORKBOOK)

    indicator, _ = results["dynamic_indicator"]
    assert any(r.fields.get("indicator_ex_tax") for r in indicator)

    labor, _ = results["labor_cost"]
    assert any(r.fields.get("actual_total_cost") for r in labor)
    assert any(
        any("2027年" in key for key in (r.monthly_data or {}))
        for r in labor
    )

    social, _ = results["social_insurance"]
    assert any(r.fields.get("estimated_total_cost") for r in social)

    site, _ = results["site_management"]
    assert any(r.fields.get("unit_price_ex_tax") for r in site)
    assert any(
        any("2027年" in key for key in (r.monthly_data or {}))
        for r in site
    )

    machinery, _ = results["machinery"]
    assert any(r.fields.get("machine_name") for r in machinery)
    assert any(r.fields.get("contract_total") for r in machinery)

    construction, _ = results["construction_dynamic"]
    assert any(r.fields.get("quota_code") for r in construction)
    assert any(r.fields.get("contract_total_price") for r in construction)
    assert any(
        any("累计结算工程量" in key for key in (r.monthly_data or {}))
        for r in construction
    )

    installation, _ = results["installation_dynamic"]
    assert any(r.fields.get("installation_fee") for r in installation)
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
    for template_id in ("dynamic_indicator", "bid_comparison", "other_items", "material_cost", "installation_dynamic"):
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
        assert template_id not in results, f"{template_id} unexpectedly matched a sheet on the old workbook"
