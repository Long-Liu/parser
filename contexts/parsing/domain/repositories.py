from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.parsing.domain.parse_job import ParseJob
from contexts.shared.domain.identifiers import JobId, ProjectId


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

    async def count(self, project_id: ProjectId | None = None) -> int:
        raise NotImplementedError


class UploadPreviewRepository(ABC):
    @abstractmethod
    async def save(
        self, batch_id: int, payload: list[dict], summary: list[dict]
    ) -> None: ...
    @abstractmethod
    async def get(self, batch_id: int) -> dict | None: ...
    @abstractmethod
    async def delete(self, batch_id: int) -> None: ...
    @abstractmethod
    async def cleanup_expired(self, max_age_hours: int = 24) -> int: ...
