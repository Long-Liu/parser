from __future__ import annotations

import re

from contexts.template.domain.template import StopRule, StopRuleType


class StopDetector:
    """Detect when to stop reading data rows based on template stop rules."""

    def match_rule(
        self,
        row_index: int,
        grid: list[list],
        stop_rules: list[StopRule],
    ) -> StopRule | None:
        """Return the first rule that fires on this row, or None."""
        for rule in stop_rules:
            if rule.rule_type == StopRuleType.CELL_MATCH:
                if self._check_cell_match(
                    grid, row_index, rule.patterns, rule.columns
                ):
                    return rule
            elif rule.rule_type == StopRuleType.CONSECUTIVE_EMPTY:
                if self._check_consecutive_empty(
                    grid, row_index, rule.empty_row_count or 5
                ):
                    return rule
        return None

    def should_stop(
        self,
        row_index: int,
        grid: list[list],
        stop_rules: list[StopRule],
    ) -> bool:
        return self.match_rule(row_index, grid, stop_rules) is not None

    def _check_cell_match(
        self, grid: list[list], row_index: int,
        patterns: list[str], columns: list[str],
    ) -> bool:
        if row_index >= len(grid):
            return True
        row = grid[row_index]
        # No columns configured → scan every cell of the row.
        col_indexes = (
            [ord(col_letter.upper()) - ord("A") for col_letter in columns]
            if columns
            else list(range(len(row)))
        )
        for col_idx in col_indexes:
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
