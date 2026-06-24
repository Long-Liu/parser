def unmerge(worksheet) -> list[list]:
    max_row = worksheet.max_row or 1
    max_col = worksheet.max_column or 1

    grid = [[None] * max_col for _ in range(max_row)]

    for row_idx, row in enumerate(worksheet.iter_rows(min_row=1, max_row=max_row, max_col=max_col, values_only=True), 1):
        for col_idx, val in enumerate(row, 1):
            grid[row_idx - 1][col_idx - 1] = val

    for merged_range in worksheet.merged_cells.ranges:
        min_col = merged_range.min_col
        min_row = merged_range.min_row
        top_left_value = grid[min_row - 1][min_col - 1]
        for r in range(merged_range.min_row, merged_range.max_row + 1):
            for c in range(merged_range.min_col, merged_range.max_col + 1):
                grid[r - 1][c - 1] = top_left_value

    return grid
