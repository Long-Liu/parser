from __future__ import annotations

from contexts.parsing.domain.pipeline_services import MergedCellRange


def worksheet_to_grid(ws) -> tuple[list[list], list[MergedCellRange]]:
    grid = [[cell.value for cell in row] for row in ws.iter_rows()]
    ranges = [
        MergedCellRange(
            min_col=merged_range.min_col - 1,
            max_col=merged_range.max_col - 1,
            min_row=merged_range.min_row - 1,
            max_row=merged_range.max_row - 1,
        )
        for merged_range in ws.merged_cells.ranges
    ]
    return grid, ranges
