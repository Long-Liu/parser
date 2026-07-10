from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.project.domain.project import Project


class ProjectRepository(ABC):
    @abstractmethod
    async def save(self, project: Project) -> None: ...
    @abstractmethod
    async def find_by_id(self, project_id: ProjectId) -> Project | None: ...
    @abstractmethod
    async def find_by_code(self, code: str) -> Project | None: ...
    @abstractmethod
    async def list_all(self) -> list[Project]: ...
    # Optional project-membership extension. Kept non-abstract so existing
    # repository fakes and integrations remain source-compatible.
    async def assign_user(self, project_id: ProjectId, user_id: UserId, is_primary: bool = False) -> None:
        raise NotImplementedError

    async def remove_user(self, project_id: ProjectId, user_id: UserId) -> None:
        raise NotImplementedError
