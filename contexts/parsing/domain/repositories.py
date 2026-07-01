from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.parsing.domain.parse_job import ParseJob, ParsedRow


class ParseJobRepository(Repository):
    @abstractmethod
    async def next_id(self) -> JobId: ...

    @abstractmethod
    async def save(self, job: ParseJob) -> None: ...

    @abstractmethod
    async def find_by_id(self, job_id: JobId) -> ParseJob | None: ...

    @abstractmethod
    async def find_by_project(
        self, project_id: ProjectId, limit: int = 20, offset: int = 0
    ) -> list[ParseJob]: ...

    @abstractmethod
    async def insert_data_rows(
        self, template_id: str, rows: list[ParsedRow]
    ) -> None: ...
