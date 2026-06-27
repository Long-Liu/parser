"""Row extraction from merged-cell grids using template column definitions."""

from core.stop_detector import StopDetector


def _pre_resolve_dynamic(dynamic_cols: list[dict], col_index: dict[str, int]) -> list[list[tuple[str, int]]]:
    """Pre-resolve which column indices match each dynamic-column definition."""
    result = []
    for dyn in dynamic_cols:
        match_terms = dyn.get("match_header", [])
        db_prefix = dyn.get("db_prefix", "monthly")
        matched = []
        for col_name, col_idx in col_index.items():
            if all(term in col_name for term in match_terms):
                parts = col_name.split("_")
                key = parts[-1] if parts else col_name
                matched.append((f"{db_prefix}_{key}", col_idx))
        result.append(matched)
    return result


def _get_cell(row: list, col_index: dict[str, int], header_name: str):
    idx = col_index.get(header_name)
    if idx is not None and idx < len(row):
        return row[idx]
    return None


def _get_cell_by_match(row: list, col_index: dict[str, int], match_terms: list[str]):
    for col_name, col_idx in col_index.items():
        if all(term in col_name for term in match_terms):
            if col_idx < len(row):
                return row[col_idx]
    return None


def _extract_row(row: list, col_index: dict[str, int],
                 columns: list[dict], dynamic_matches: list[list[tuple[str, int]]],
                 hierarchy_col_name: str) -> dict:
    record = {"hierarchy_code": _get_cell(row, col_index, hierarchy_col_name)}

    for col_def in columns:
        db_field = col_def["db_field"]
        match_terms = col_def.get("match_header", [])
        record[db_field] = _get_cell_by_match(row, col_index, match_terms)

    monthly = {}
    for matched in dynamic_matches:
        for key, col_idx in matched:
            monthly[key] = row[col_idx] if col_idx < len(row) else None
    record["monthly_data"] = monthly

    return record


def extract_rows(grid: list[list], flat_headers: list[str], config: dict) -> list[dict]:
    """Extract rows from a merged-cell grid using template config column definitions."""
    columns = config.get("columns", [])
    dynamic_cols = config.get("dynamic_columns", [])
    hierarchy = config.get("hierarchy", {})
    hierarchy_col_name = hierarchy.get("column_name", "序号")
    data_start = config.get("headers", {}).get("data_start_row", 1)
    stop_rules = config.get("stop_rules", [])

    detector = StopDetector(stop_rules)
    col_index = {name: idx for idx, name in enumerate(flat_headers)}
    dynamic_matches = _pre_resolve_dynamic(dynamic_cols, col_index)

    results = []
    for row_idx in range(data_start - 1, len(grid)):
        row = grid[row_idx]

        action = detector.check(row, col_index)

        if action == "stop":
            break

        # Skip empty rows
        if all(v is None or str(v).strip() == "" for v in row):
            continue

        record = _extract_row(row, col_index, columns, dynamic_matches, hierarchy_col_name)
        results.append(record)

        if action == "last":
            break

    return results
