"""Flatten multi-row merged headers into single column names."""


def flatten_headers(grid: list[list], header_rows: list[int]) -> list[str]:
    """Concatenate multi-row header values into column names joined by '_'."""
    if not grid or not header_rows:
        return []

    num_cols = max(len(row) for row in grid)
    result = []

    for col_idx in range(num_cols):
        parts = []
        for row_idx in header_rows:
            if row_idx < len(grid) and col_idx < len(grid[row_idx]):
                val = grid[row_idx][col_idx]
                if val is not None:
                    s = str(val).strip()
                    if s:
                        parts.append(s)
        result.append("_".join(parts))

    return result
