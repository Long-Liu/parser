"""Tests for parsing domain services."""

from contexts.parsing.domain.cell_unmerger import CellUnmerger, MergedCellRange
from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.data_validator import DataValidator
from contexts.parsing.domain.header_flattener import HeaderFlattener
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.template.domain.template import (
    ColumnMapping,
    HeaderSpec,
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


# ── StopDetector ─────────────────────────────────────────────────────

def test_stop_on_cell_match():
    detector = StopDetector()
    grid = [
        ["Data", "Value"],
        ["合计", "100"],
        ["More", "200"],
    ]
    stop_rules = [
        StopRule(
            rule_type=StopRuleType.CELL_MATCH,
            patterns=[r"^合.*"],
            columns=["A"],
        ),
    ]
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
    stop_rules = [
        StopRule(
            rule_type=StopRuleType.CONSECUTIVE_EMPTY,
            patterns=[],
            columns=[],
            empty_row_count=5,
        ),
    ]
    assert detector.should_stop(0, grid, stop_rules) is False
    assert detector.should_stop(1, grid, stop_rules) is True


def test_stop_past_grid_end():
    detector = StopDetector()
    stop_rules = [
        StopRule(
            rule_type=StopRuleType.CELL_MATCH,
            patterns=[r".*"],
            columns=["A"],
        ),
    ]
    assert detector.should_stop(100, [["A"]], stop_rules) is True


# ── DataValidator ────────────────────────────────────────────────────

def _make_template(**kwargs) -> Template:
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
    return Template(**defaults)


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
