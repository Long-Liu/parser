from __future__ import annotations

import re

from contexts.template.domain.template import StopRule, StopRuleType


class StopDetector:
    """Detect when to stop reading data rows based on template stop rules."""

    def should_stop(
        self,
        row_index: int,
        grid: list[list],
        stop_rules: list[StopRule],
    ) -> bool:
        for rule in stop_rules:
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

    def _check_cell_match(
        self, grid: list[list], row_index: int,
        patterns: list[str], columns: list[str],
    ) -> bool:
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

    def _check_consecutive_empty(
        self, grid: list[list], row_index: int, count: int,
    ) -> bool:
        for i in range(count):
            check_idx = row_index + i
            if check_idx >= len(grid):
                return True
            if any(v is not None for v in grid[check_idx]):
                return False
        return True
