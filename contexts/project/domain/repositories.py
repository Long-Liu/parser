from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import ProjectId
from contexts.project.domain.project import Project


class ProjectRepository(Repository):
    @abstractmethod
    async def next_id(self) -> ProjectId: ...
    @abstractmethod
    async def save(self, project: Project) -> None: ...
    @abstractmethod
    async def find_by_id(self, project_id: ProjectId) -> Project | None: ...
    @abstractmethod
    async def find_by_code(self, code: str) -> Project | None: ...
    @abstractmethod
    async def list_all(self) -> list[Project]: ...
