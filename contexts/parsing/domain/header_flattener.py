from __future__ import annotations


class HeaderFlattener:
    """Flatten multi-row headers into single-row column names."""

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
