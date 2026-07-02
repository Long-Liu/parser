from __future__ import annotations

from contexts.parsing.domain.parse_job import ParsedRow
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.template.domain.template import Template


class DataRowExtractor:
    """Extract data rows from a worksheet grid using a template spec."""

    def __init__(self, stop_detector: StopDetector | None = None) -> None:
        self._stop_detector = stop_detector or StopDetector()

    def extract(
        self, grid: list[list], flat_headers: list[str], template: Template
    ) -> list[ParsedRow]:
        data_start = template.header_spec.data_start_row - 1
        rows = []
        for ri in range(data_start, len(grid)):
            if self._stop_detector.should_stop(ri, grid, template.stop_rules):
                break
            row_data = self._extract_row(grid[ri], flat_headers, template)
            if row_data is not None:
                rows.append(ParsedRow(
                    row_index=ri + 1,
                    fields=row_data.fields,
                    hierarchy_code=row_data.hierarchy_code,
                    monthly_data=row_data.monthly_data,
                ))
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
