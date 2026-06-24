from core.stop_detector import StopDetector


class DataExtractor:
    def __init__(self, config: dict):
        self.config = config
        self.columns = config.get("columns", [])
        self.dynamic_cols = config.get("dynamic_columns", [])
        hierarchy = config.get("hierarchy", {})
        self.hierarchy_col_name = hierarchy.get("column_name", "序号")
        self.data_start = config.get("headers", {}).get("data_start_row", 1)
        stop_rules = config.get("stop_rules", [])
        self.stop_detector = StopDetector(stop_rules)

    def extract_rows(self, grid: list[list], flat_headers: list[str]) -> list[dict]:
        col_index = {name: idx for idx, name in enumerate(flat_headers)}
        letter_map = {chr(65 + i): i for i in range(len(flat_headers))}

        results = []
        for row_idx in range(self.data_start - 1, len(grid)):
            row = grid[row_idx]

            if self.stop_detector.check(row, letter_map):
                break

            record = self._extract_row(row, col_index)
            results.append(record)

        return results

    def _extract_row(self, row: list, col_index: dict[str, int]) -> dict:
        record = {}

        record["hierarchy_code"] = self._get_cell(row, col_index, self.hierarchy_col_name)

        for col_def in self.columns:
            db_field = col_def["db_field"]
            match_terms = col_def.get("match_header", [])
            record[db_field] = self._get_cell_by_match(row, col_index, match_terms)

        monthly = {}
        for dyn in self.dynamic_cols:
            db_prefix = dyn.get("db_prefix", "monthly")
            match_terms = dyn.get("match_header", [])

            for col_name, col_idx in col_index.items():
                if all(term in col_name for term in match_terms):
                    parts = col_name.split("_")
                    key = parts[-1] if parts else col_name
                    monthly[f"{db_prefix}_{key}"] = row[col_idx] if col_idx < len(row) else None

        record["monthly_data"] = monthly
        return record

    def _get_cell(self, row, col_index, header_name):
        idx = col_index.get(header_name)
        if idx is not None and idx < len(row):
            return row[idx]
        return None

    def _get_cell_by_match(self, row, col_index, match_terms):
        for col_name, col_idx in col_index.items():
            if all(term in col_name for term in match_terms):
                if col_idx < len(row):
                    return row[col_idx]
        return None
