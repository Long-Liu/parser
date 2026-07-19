from __future__ import annotations

from contexts.parsing.domain.hierarchy_code import (
    parse_hierarchy_code,
    strip_whitespace,
)
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.template.domain.template import StopRuleAction, Template


class DataRowExtractor:
    """Extract data rows from a worksheet grid using a template spec."""

    def __init__(self, stop_detector: StopDetector | None = None) -> None:
        self._stop_detector = stop_detector or StopDetector()

    def extract(
        self, grid: list[list], flat_headers: list[str], template: Template
    ) -> list[ParsedRow]:
        data_start = template.header_spec.data_start_row - 1
        hierarchy_col = self._resolve_hierarchy_column(grid, template)
        separator = (
            template.hierarchy_config.separator
            if template.hierarchy_config is not None
            else "."
        )
        rows = []
        for ri in range(data_start, len(grid)):
            fired = self._stop_detector.match_rule(ri, grid, template.stop_rules)
            if fired is not None:
                if fired.action == StopRuleAction.LAST:
                    self._append_row(
                        rows, grid, ri, flat_headers, template,
                        hierarchy_col, separator,
                    )
                break
            self._append_row(
                rows, grid, ri, flat_headers, template,
                hierarchy_col, separator,
            )
        return rows

    def _append_row(
        self, rows: list[ParsedRow], grid: list[list], ri: int,
        flat_headers: list[str], template: Template,
        hierarchy_col: int | None, separator: str,
    ) -> None:
        row = grid[ri]
        row_data = self._extract_row(row, flat_headers, template)
        if row_data is None:
            return
        hierarchy_code = None
        if hierarchy_col is not None and hierarchy_col < len(row):
            hierarchy_code = parse_hierarchy_code(row[hierarchy_col], separator)
        rows.append(ParsedRow(
            row_index=ri + 1,
            fields=row_data.fields,
            hierarchy_code=hierarchy_code,
            monthly_data=row_data.monthly_data,
        ))

    def _resolve_hierarchy_column(
        self, grid: list[list], template: Template
    ) -> int | None:
        """Locate the hierarchy column by matching the configured column name
        against raw header cells (whitespace-insensitive).

        YAML ``headers.rows`` are 1-based Excel row numbers; fall back to any
        row above the data area when the configured rows do not match.
        """
        config = template.hierarchy_config
        if config is None or not config.column_name:
            return None
        target = strip_whitespace(config.column_name)
        if not target:
            return None
        data_start = max(template.header_spec.data_start_row - 1, 0)
        preferred = [
            r - 1 for r in template.header_spec.header_rows if 0 < r <= len(grid)
        ]
        candidates = preferred + [
            r for r in range(min(data_start, len(grid))) if r not in preferred
        ]
        for r in candidates:
            for ci, cell in enumerate(grid[r]):
                if cell is not None and strip_whitespace(str(cell)) == target:
                    return ci
        return None

    def _extract_row(
        self, row: list, flat_headers: list[str], template: Template
    ) -> ParsedRow | None:
        fields: dict = {}
        monthly_data: dict = {}
        for ci, header in enumerate(flat_headers):
            if ci >= len(row):
                continue
            value = row[ci]
            fixed = template.find_column(header)
            if fixed:
                fields[fixed.db_field] = value
                continue
            dyn = template.find_dynamic_column(header)
            if dyn:
                monthly_data[f"{dyn.db_prefix}_{header}"] = value
                continue
        if fields:
            return ParsedRow(
                row_index=-1,
                fields=fields,
                monthly_data=monthly_data if monthly_data else None,
            )
        return None
