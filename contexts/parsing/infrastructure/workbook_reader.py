from __future__ import annotations

import asyncio
from contextlib import closing

import openpyxl

from contexts.parsing.domain.pipeline_services import MergedCellRange
from contexts.parsing.domain.workbook import WorkbookReader, WorkbookSheet


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


class OpenPyxlWorkbookReader(WorkbookReader):
    async def read(self, filepath: str) -> list[WorkbookSheet]:
        wb = await asyncio.to_thread(openpyxl.load_workbook, filepath, data_only=True)
        with closing(wb):
            sheets = []
            for sheet_name in wb.sheetnames:
                grid, ranges = worksheet_to_grid(wb[sheet_name])
                sheets.append(
                    WorkbookSheet(name=sheet_name, grid=grid, merged_ranges=ranges)
                )
            return sheets
