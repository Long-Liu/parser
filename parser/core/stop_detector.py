import re


class StopDetector:
    def __init__(self, rules: list[dict]):
        self.rules = rules or []
        self.consecutive_empty = 0

    def check(self, row: list, col_map: dict[str, int]) -> bool:
        for rule in self.rules:
            if rule["type"] == "cell_match":
                if self._check_cell_match(row, col_map, rule):
                    return True
            elif rule["type"] == "consecutive_empty_rows":
                if self._check_consecutive_empty(row, rule):
                    return True
        self._update_empty_counter(row)
        return False

    def _check_cell_match(self, row, col_map, rule) -> bool:
        patterns = rule.get("patterns", [])
        columns = rule.get("columns", [])
        for col_letter in columns:
            idx = col_map.get(col_letter)
            if idx is None or idx >= len(row):
                continue
            val = str(row[idx]) if row[idx] is not None else ""
            for pat in patterns:
                if re.match(pat, val):
                    return True
        return False

    def _check_consecutive_empty(self, row, rule) -> bool:
        count = rule.get("count", 5)
        return self.consecutive_empty + 1 >= count

    def _update_empty_counter(self, row):
        if all(v is None or str(v).strip() == "" for v in row):
            self.consecutive_empty += 1
        else:
            self.consecutive_empty = 0
