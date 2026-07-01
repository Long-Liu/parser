# ponytail: adapted from core/ — cell_unmerger, header_flattener, stop_detector,
# data_extractor, validator. Logic unchanged, reorganized as DDD domain services.

from __future__ import annotations

import re

from contexts.parsing.domain.parse_job import ParsedRow, RowError
from contexts.template.domain.template import Template, StopRuleType


class CellUnmerger:
    def unmerge(self, ws) -> list[list]:
        grid = [[cell.value for cell in row] for row in ws.iter_rows()]
        for merged_range in ws.merged_cells.ranges:
            min_col = merged_range.min_col - 1
            max_col = merged_range.max_col - 1
            min_row = merged_range.min_row - 1
            max_row = merged_range.max_row - 1
            value = (
                grid[min_row][min_col]
                if min_row < len(grid) and min_col < len(grid[min_row])
                else None
            )
            for r in range(min_row, min(max_row + 1, len(grid))):
                row_len = len(grid[r]) if r < len(grid) else 0
                for c in range(min_col, min(max_col + 1, row_len)):
                    if r < len(grid) and c < len(grid[r]):
                        grid[r][c] = value
        return grid


class HeaderFlattener:
    def flatten(self, grid: list[list], header_rows: list[int]) -> list[str]:
        if not grid or not header_rows:
            return []
        max_cols = max(
            (len(grid[r]) for r in header_rows if r < len(grid)), default=0
        )
        names = []
        for col in range(max_cols):
            parts = []
            for row_idx in header_rows:
                if row_idx < len(grid) and col < len(grid[row_idx]):
                    v = grid[row_idx][col]
                    if v is not None and str(v).strip():
                        parts.append(str(v).strip())
            names.append("_".join(parts))
        return names


class StopDetector:
    def should_stop(
        self, row_index: int, grid: list[list], template: Template
    ) -> bool:
        for rule in template.stop_rules:
            if rule.rule_type == StopRuleType.CELL_MATCH:
                if self._check_cell_match(
                    grid, row_index, rule.patterns, rule.columns
                ):
                    return True
            elif rule.rule_type == StopRuleType.CONSECUTIVE_EMPTY:
                if self._check_consecutive_empty(
                    grid, row_index, rule.empty_row_count or 5
                ):
                    return True
        return False

    def _check_cell_match(self, grid, row_index, patterns, columns) -> bool:
        if row_index >= len(grid):
            return True
        row = grid[row_index]
        for col_letter in columns or []:
            col_idx = ord(col_letter.upper()) - ord("A")
            if col_idx < len(row) and row[col_idx] is not None:
                text = str(row[col_idx])
                for pattern in patterns:
                    if re.match(pattern, text):
                        return True
        return False

    def _check_consecutive_empty(self, grid, row_index, count) -> bool:
        for i in range(count):
            check_idx = row_index + i
            if check_idx >= len(grid):
                return True
            if any(v is not None for v in grid[check_idx]):
                return False
        return True


class DataRowExtractor:
    def extract(
        self, grid: list[list], flat_headers: list[str], template: Template
    ) -> list[ParsedRow]:
        data_start = template.header_spec.data_start_row - 1
        stop_detector = StopDetector()
        rows = []
        for ri in range(data_start, len(grid)):
            if stop_detector.should_stop(ri, grid, template):
                break
            row_data = self._extract_row(grid[ri], flat_headers, template)
            if row_data is not None:
                rows.append(row_data)
        return rows

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


class DataValidator:
    def validate(
        self, rows: list[ParsedRow], template: Template
    ) -> tuple[list[ParsedRow], list[RowError]]:
        valid: list[ParsedRow] = []
        errors: list[RowError] = []
        for row in rows:
            row_errors = self._validate_row(row, template)
            if row_errors:
                errors.extend(row_errors)
            else:
                valid.append(row)
        return valid, errors

    def _validate_row(self, row: ParsedRow, template: Template) -> list[RowError]:
        errs: list[RowError] = []
        for col in template.fixed_columns:
            if col.db_field in row.fields:
                value = row.fields[col.db_field]
                if value is not None and col.db_type.startswith("decimal"):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errs.append(RowError(
                            row_index=row.row_index,
                            field=col.db_field,
                            value=str(value),
                            reason="expected decimal",
                        ))
        return errs
