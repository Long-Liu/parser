from __future__ import annotations

from abc import abstractmethod

from contexts.parsing.domain.parse_job import ParsedRow


class ParsedDataSink:
    @abstractmethod
    async def insert_data_rows(
        self, template_id: str, batch_id: int, rows: list[ParsedRow]
    ) -> None: ...
