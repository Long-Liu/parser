"""Tests for parsing domain services."""

from datetime import date, datetime
from decimal import Decimal
from typing import cast

from contexts.parsing.domain.cell_unmerger import CellUnmerger, MergedCellRange
from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.data_validator import DataValidator
from contexts.parsing.domain.header_flattener import HeaderFlattener
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.parsing.domain.template_spec import StopRuleSpec, TemplateSpec

# noinspection PyProtectedMember
from contexts.parsing.infrastructure.data_writer import _model_values
from contexts.shared.infrastructure.database.tables import (
    DataDynamicIndicator,
    DataSettlementOutput,
)
from contexts.template.domain.template import (
    ColumnMapping,
    HeaderSpec,
    HierarchyConfig,
    StopRule,
    StopRuleType,
    Template,
    TemplateId,
)

# ── CellUnmerger ─────────────────────────────────────────────────────


def test_unmerge_fills_merged_cells():
    unmerger = CellUnmerger()
    grid = [
        ["H1", None, "H3"],
        [None, "B2", None],
    ]
    ranges = [MergedCellRange(min_col=0, max_col=1, min_row=0, max_row=1)]
    result = unmerger.unmerge(grid, ranges)
    assert result[0][0] == "H1"
    assert result[0][1] == "H1"  # filled from merge
    assert result[1][0] == "H1"  # filled from merge
    assert result[1][1] == "H1"  # filled from merge (inside 2×2 merged area)
    assert result[0][2] == "H3"  # untouched (outside merged columns)


def test_unmerge_empty_ranges_noop():
    unmerger = CellUnmerger()
    grid = [["A", "B"], ["C", "D"]]
    result = unmerger.unmerge(grid, [])
    assert result == grid


# ── HeaderFlattener ──────────────────────────────────────────────────


def test_flatten_single_row_header():
    flattener = HeaderFlattener()
    grid = [["Name", "Amount", "Date"]]
    result = flattener.flatten(grid, [0])
    assert result == ["Name", "Amount", "Date"]


def test_flatten_multi_row_header():
    flattener = HeaderFlattener()
    grid = [
        ["Person", "Finance", ""],
        ["Name", "Amount", "Date"],
    ]
    result = flattener.flatten(grid, [0, 1])
    assert result == ["Person_Name", "Finance_Amount", "Date"]


def test_flatten_empty_grid():
    flattener = HeaderFlattener()
    assert flattener.flatten([], [0]) == []
    assert flattener.flatten([["A"]], []) == []


def test_extractor_can_map_duplicate_header_by_occurrence():
    template = cast(
        TemplateSpec,
        cast(
            object,
            Template(
                template_id=TemplateId("duplicate_headers"),
                header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
                fixed_columns=[
                    ColumnMapping("first_note", ["备注"]),
                    ColumnMapping("final_note", ["备注"], occurrence=2),
                ],
            ),
        ),
    )
    rows = DataRowExtractor().extract(
        [["备注", "备注"], ["前备注", "后备注"]],
        ["备注", "备注"],
        template,
    )
    assert rows[0].fields == {
        "first_note": "前备注",
        "final_note": "后备注",
    }


# ── StopDetector ─────────────────────────────────────────────────────


def test_stop_on_cell_match():
    detector = StopDetector()
    grid = [
        ["Data", "Value"],
        ["合计", "100"],
        ["More", "200"],
    ]
    stop_rules = cast(
        list[StopRuleSpec],
        cast(
            object,
            [
                StopRule(
                    rule_type=StopRuleType.CELL_MATCH,
                    patterns=[r"^合.*"],
                    columns=["A"],
                ),
            ],
        ),
    )
    assert detector.should_stop(0, grid, stop_rules) is False
    assert detector.should_stop(1, grid, stop_rules) is True


def test_stop_on_consecutive_empty():
    detector = StopDetector()
    grid = [
        ["A", "B"],
        [None, None],
        [None, None],
        [None, None],
        [None, None],
        [None, None],
    ]
    stop_rules = cast(
        list[StopRuleSpec],
        cast(
            object,
            [
                StopRule(
                    rule_type=StopRuleType.CONSECUTIVE_EMPTY,
                    patterns=[],
                    columns=[],
                    empty_row_count=5,
                ),
            ],
        ),
    )
    assert detector.should_stop(0, grid, stop_rules) is False
    assert detector.should_stop(1, grid, stop_rules) is True


def test_stop_past_grid_end():
    detector = StopDetector()
    stop_rules = cast(
        list[StopRuleSpec],
        cast(
            object,
            [
                StopRule(
                    rule_type=StopRuleType.CELL_MATCH,
                    patterns=[r".*"],
                    columns=["A"],
                ),
            ],
        ),
    )
    assert detector.should_stop(100, [["A"]], stop_rules) is True


# ── DataValidator ────────────────────────────────────────────────────


def _make_template(**kwargs) -> TemplateSpec:
    defaults = dict(
        template_id=TemplateId("test"),
        description="test",
        sheet_pattern="*",
        header_spec=HeaderSpec(header_rows=[0], data_start_row=1),
        stop_rules=[],
        fixed_columns=[ColumnMapping(db_field="amount", match_headers=["Amount"], db_type="decimal(15,2)")],
        dynamic_columns=[],
    )
    defaults.update(kwargs)
    # Template structurally satisfies TemplateSpec (duck-typed protocol).
    return cast(TemplateSpec, cast(object, Template(**defaults)))


def test_validate_decimal_field():
    validator = DataValidator()
    template = _make_template()
    rows = [
        ParsedRow(row_index=1, fields={"amount": 100}),
        ParsedRow(row_index=2, fields={"amount": "not_a_number"}),
    ]
    valid, errors = validator.validate(rows, template)
    assert len(valid) == 1
    assert valid[0].fields["amount"] == 100
    assert len(errors) == 1
    assert errors[0].row_index == 2
    assert errors[0].field == "amount"
    assert "decimal" in errors[0].reason


def test_validate_skips_non_decimal_fields():
    validator = DataValidator()
    template = _make_template(
        fixed_columns=[ColumnMapping(db_field="name", match_headers=["Name"], db_type="varchar(255)")],
    )
    rows = [ParsedRow(row_index=1, fields={"name": 123})]  # non-string OK for varchar
    valid, errors = validator.validate(rows, template)
    assert len(valid) == 1
    assert len(errors) == 0


def test_validate_all_valid():
    validator = DataValidator()
    template = _make_template()
    rows = [
        ParsedRow(row_index=1, fields={"amount": 10.5}),
        ParsedRow(row_index=2, fields={"amount": 0}),
    ]
    valid, errors = validator.validate(rows, template)
    assert len(valid) == 2
    assert len(errors) == 0


def _date_template(db_type: str) -> TemplateSpec:
    return _make_template(
        fixed_columns=[ColumnMapping(db_field="when", match_headers=["When"], db_type=db_type)],
    )


def test_validate_normalizes_lenient_date_strings_to_iso():
    """Non-ISO date text passes validation but must be normalized to the ISO
    string Tortoise DateField/DatetimeField can parse — otherwise the raw
    string reaches MySQL strict mode and aborts the whole batch insert."""
    validator = DataValidator()
    template = _date_template("date")
    for raw in ("2026/07/15", "2026.07.15", "2026年7月15日", "2026-07-15", "2026-07-15T10:30:00"):
        valid, errors = validator.validate([ParsedRow(row_index=1, fields={"when": raw})], template)
        assert not errors, f"{raw!r} should be valid"
        assert valid[0].fields["when"] == "2026-07-15", f"{raw!r} normalized to {valid[0].fields['when']!r}"


def test_validate_normalizes_native_datetime_to_iso():
    validator = DataValidator()
    template = _date_template("date")
    valid, errors = validator.validate([ParsedRow(row_index=1, fields={"when": datetime(2026, 7, 15, 10, 30)})], template)
    assert not errors
    assert valid[0].fields["when"] == "2026-07-15"  # time truncated for a date column

    template = _date_template("datetime")
    valid, errors = validator.validate([ParsedRow(row_index=1, fields={"when": date(2026, 7, 15)})], template)
    assert not errors
    assert valid[0].fields["when"] == "2026-07-15T00:00:00"


def test_validate_rejects_freeform_datetime_text():
    """Free-form text (no parseable date) is rejected rather than let through
    to abort the batch insert."""
    validator = DataValidator()
    template = _date_template("date")
    for raw in ("2027年6月", "abc", "not-a-date", "2026-13-99"):
        valid, errors = validator.validate([ParsedRow(row_index=1, fields={"when": raw})], template)
        assert not valid, f"{raw!r} should be rejected"
        assert len(errors) == 1
        assert "expected date" in errors[0].reason


def test_data_writer_normalizes_float_for_decimal_column():
    values = _model_values(
        DataSettlementOutput,
        {"cumulative_value": 3.315, "indicator_name": "x"},
    )
    assert values["cumulative_value"] == Decimal("3.315000")
    assert values["indicator_name"] == "x"
    dynamic = _model_values(DataDynamicIndicator, {"indicator_with_tax": 58.625})
    assert dynamic["indicator_with_tax"] == Decimal("58.63")


# ── DataRowExtractor ─────────────────────────────────────────────────


def test_extract_with_fixed_columns():
    extractor = DataRowExtractor()
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
    )
    grid = [
        ["Amount"],
        [100],
        [200],
    ]
    flat_headers = ["Amount"]
    rows = extractor.extract(grid, flat_headers, template)
    assert len(rows) == 2
    assert rows[0].fields["amount"] == 100
    assert rows[1].fields["amount"] == 200


def test_extract_preserves_populated_unmapped_columns_in_monthly_data():
    extractor = DataRowExtractor()
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
        hierarchy_config=None,
    )
    grid = [
        ["Amount", "Unmodeled detail", "Another detail"],
        [100, "kept", 3.5],
    ]
    rows = extractor.extract(
        grid,
        ["Amount", "Unmodeled detail", "Another detail"],
        template,
    )
    assert rows[0].monthly_data == {
        "extra_col_2_Unmodeled detail": "kept",
        "extra_col_3_Another detail": 3.5,
    }


def test_extract_converts_unmapped_dates_to_json_safe_values():
    extractor = DataRowExtractor()
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
    )
    rows = extractor.extract(
        [["Amount", "Unmodeled date"], [1, datetime(2026, 7, 30, 8, 15)]],
        ["Amount", "Unmodeled date"],
        template,
    )
    assert rows[0].monthly_data == {
        "extra_col_2_Unmodeled date": "2026-07-30T08:15:00",
    }


def test_extract_does_not_duplicate_hierarchy_column_as_extra_data():
    extractor = DataRowExtractor()
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
        hierarchy_config=HierarchyConfig(column_name="序号", separator="."),
    )
    grid = [
        ["序号", "Amount"],
        ["1.2", 100],
    ]
    rows = extractor.extract(grid, ["序号", "Amount"], template)
    assert rows[0].hierarchy_code == "1.2"
    assert rows[0].monthly_data is None


def test_extract_keeps_row_with_only_unmapped_business_data():
    extractor = DataRowExtractor()
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
    )
    rows = extractor.extract(
        [["Supplement", "Amount"], ["must survive"]],
        ["Supplement", "Amount"],
        template,
    )
    assert len(rows) == 1
    assert rows[0].fields == {}
    assert rows[0].monthly_data == {
        "extra_col_1_Supplement": "must survive",
    }


def test_extract_skips_fully_blank_source_row_with_mapped_headers():
    extractor = DataRowExtractor()
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
    )
    rows = extractor.extract(
        [["Amount", "Supplement"], [None, None]],
        ["Amount", "Supplement"],
        template,
    )
    assert rows == []


def test_extract_stops_at_stop_rule():
    stop_detector = StopDetector()
    extractor = DataRowExtractor(stop_detector)
    template = _make_template(
        header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
        stop_rules=[
            StopRule(
                rule_type=StopRuleType.CELL_MATCH,
                patterns=[r"^停$"],
                columns=["A"],
            ),
        ],
    )
    grid = [
        ["Amount"],
        [100],
        ["停"],
        [200],  # should not be extracted
    ]
    flat_headers = ["Amount"]
    rows = extractor.extract(grid, flat_headers, template)
    assert len(rows) == 1
    assert rows[0].fields["amount"] == 100
