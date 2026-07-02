from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.parsing.domain.parse_job import ParseJob


class ParseJobRepository(ABC):
    @abstractmethod
    async def save(self, job: ParseJob) -> None: ...

    @abstractmethod
    async def find_by_id(self, job_id: JobId) -> ParseJob | None: ...

    @abstractmethod
    async def find_by_project(
        self, project_id: ProjectId, limit: int = 20, offset: int = 0
    ) -> list[ParseJob]: ...

    @abstractmethod
    async def list_recent(self, limit: int = 100, offset: int = 0) -> list[ParseJob]: ...
