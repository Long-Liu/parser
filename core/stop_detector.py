"""Stop-detection rules for early termination of row scanning."""

import re

import openpyxl.utils

DEFAULT_CONSECUTIVE_EMPTY_COUNT = 5

# Return values: "continue" | "stop" | "last"
# "stop" = stop BEFORE this row (annotation markers like "注：")
# "last" = extract this row THEN stop (data markers like "合计")


class StopDetector:
    """Evaluate rows against configurable stop rules (cell_match, consecutive_empty)."""

    def __init__(self, rules: list[dict]):
        clean_rules = rules or []
        self.rules = clean_rules
        self.consecutive_empty = 0
        self._compiled_rules = self._precompile(clean_rules)

    def reset(self):
        """Reset internal state so this detector can be reused across sheets."""
        self.consecutive_empty = 0

    @staticmethod
    def _precompile(rules: list[dict]) -> list[dict]:
        compiled = []
        for rule in rules:
            entry = dict(rule)
            if rule.get("type") == "cell_match":
                entry["_patterns"] = [re.compile(p) for p in rule.get("patterns", [])]
            compiled.append(entry)
        return compiled

    def check(self, row: list, col_map: dict[str, int]) -> str:
        """Return 'continue', 'stop', or 'last'."""
        result = "continue"
        for rule in self._compiled_rules:
            if rule["type"] == "cell_match":
                if self._check_cell_match(row, rule):
                    return rule.get("action", "stop")
            elif rule["type"] == "consecutive_empty_rows":
                if self._check_consecutive_empty(row, rule):
                    result = "stop"
        self._update_empty_counter(row)
        return result

    @staticmethod
    def _column_index(col_letter: str) -> int | None:
        """Convert column letter(s) A..ZZ to 0-based index, or None if invalid."""
        try:
            return openpyxl.utils.column_index_from_string(col_letter) - 1
        except ValueError:
            return None

    def _check_cell_match(self, row, rule) -> bool:
        patterns = rule.get("_patterns", [])
        columns = rule.get("columns", [])
        indices = [StopDetector._column_index(c) for c in columns] if columns else list(range(len(row)))
        for idx in indices:
            if idx is None or idx >= len(row):
                continue
            val = str(row[idx]) if row[idx] is not None else ""
            for pat in patterns:
                if pat.match(val):
                    return True
        return False

    def _check_consecutive_empty(self, row, rule) -> bool:
        count = rule.get("count", DEFAULT_CONSECUTIVE_EMPTY_COUNT)
        return self.consecutive_empty + 1 >= count

    def _update_empty_counter(self, row):
        if all(v is None or str(v).strip() == "" for v in row):
            self.consecutive_empty += 1
        else:
            self.consecutive_empty = 0
