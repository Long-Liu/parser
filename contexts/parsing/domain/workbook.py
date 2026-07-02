from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from contexts.parsing.domain.pipeline_services import MergedCellRange


@dataclass(frozen=True)
class WorkbookSheet:
    name: str
    grid: list[list]
    merged_ranges: list[MergedCellRange]


class WorkbookReader(ABC):
    @abstractmethod
    async def read(self, filepath: str) -> list[WorkbookSheet]: ...

