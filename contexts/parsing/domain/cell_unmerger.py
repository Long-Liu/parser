from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class MergedCellRange:
    min_col: int
    max_col: int
    min_row: int
    max_row: int


class CellUnmerger:
    """Fill merged-cell regions so every cell carries the merged value."""

    def unmerge(
        self, grid: list[list], merged_ranges: list[MergedCellRange]
    ) -> list[list]:
        # ponytail: deepcopy avoids mutating caller's grid; acceptable for typical worksheet sizes
        result = deepcopy(grid)
        for merged_range in merged_ranges:
            min_col = merged_range.min_col
            max_col = merged_range.max_col
            min_row = merged_range.min_row
            max_row = merged_range.max_row
            value = (
                result[min_row][min_col]
                if min_row < len(result) and min_col < len(result[min_row])
                else None
            )
            for r in range(min_row, min(max_row + 1, len(result))):
                row_len = len(result[r]) if r < len(result) else 0
                for c in range(min_col, min(max_col + 1, row_len)):
                    if r < len(result) and c < len(result[r]):
                        result[r][c] = value
        return result
