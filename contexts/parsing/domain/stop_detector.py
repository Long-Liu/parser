from __future__ import annotations

import re

from contexts.parsing.domain.template_spec import StopRuleSpec
from contexts.shared.domain.stop_rules import StopRuleType


class StopDetector:
    """Detect when to stop reading data rows based on template stop rules."""

    def __init__(self) -> None:
        # Same rule patterns are evaluated on every data row; compile each once.
        self._pattern_cache: dict[tuple[str, ...], tuple[re.Pattern, ...]] = {}

    def _compiled_patterns(self, patterns: list[str]) -> tuple[re.Pattern, ...]:
        key = tuple(patterns)
        compiled = self._pattern_cache.get(key)
        if compiled is None:
            compiled = tuple(re.compile(pattern) for pattern in patterns)
            self._pattern_cache[key] = compiled
        return compiled

    def match_rule(
        self,
        row_index: int,
        grid: list[list],
        stop_rules: list[StopRuleSpec],
    ) -> StopRuleSpec | None:
        """Return the first rule that fires on this row, or None."""
        for rule in stop_rules:
            if rule.rule_type == StopRuleType.CELL_MATCH and self._check_cell_match(
                grid, row_index, self._compiled_patterns(rule.patterns), rule.columns
            ):
                return rule
            if rule.rule_type == StopRuleType.CONSECUTIVE_EMPTY and self._check_consecutive_empty(
                grid, row_index, rule.empty_row_count or 5
            ):
                return rule
        return None

    def should_stop(
        self,
        row_index: int,
        grid: list[list],
        stop_rules: list[StopRuleSpec],
    ) -> bool:
        return self.match_rule(row_index, grid, stop_rules) is not None

    @staticmethod
    def _column_index(col_letter: str) -> int:
        """Convert an Excel column letter (A, Z, AA, …) to a 0-based index."""
        index = 0
        for ch in col_letter.upper():
            index = index * 26 + (ord(ch) - ord("A") + 1)
        return index - 1

    @classmethod
    def _check_cell_match(
        cls,
        grid: list[list],
        row_index: int,
        patterns: tuple[re.Pattern, ...],
        columns: list[str],
    ) -> bool:
        if row_index >= len(grid):
            return True
        row = grid[row_index]
        # No columns configured → scan every cell of the row.
        col_indexes = [cls._column_index(col_letter) for col_letter in columns] if columns else list(range(len(row)))
        for col_idx in col_indexes:
            if col_idx < len(row) and row[col_idx] is not None:
                text = str(row[col_idx])
                for pattern in patterns:
                    if pattern.match(text):
                        return True
        return False

    @staticmethod
    def _check_consecutive_empty(
        grid: list[list],
        row_index: int,
        count: int,
    ) -> bool:
        for i in range(count):
            check_idx = row_index + i
            if check_idx >= len(grid):
                return True
            if any(v is not None for v in grid[check_idx]):
                return False
        return True
