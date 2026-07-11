from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.project.domain.project import Project
from contexts.shared.domain.identifiers import ProjectId, UserId


class ProjectRepository(ABC):
    @abstractmethod
    async def save(self, project: Project) -> None: ...
    @abstractmethod
    async def find_by_id(self, project_id: ProjectId) -> Project | None: ...
    @abstractmethod
    async def find_by_code(self, code: str) -> Project | None: ...
    @abstractmethod
    async def list_all(
        self,
        *,
        keyword: str = "",
        status: str = "",
        user_id: UserId | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Project], int]: ...
    async def delete(self, project_id: ProjectId) -> None: ...
    # Optional project-membership extension. Kept non-abstract so existing
    # repository fakes and integrations remain source-compatible.
    async def assign_user(
        self,
        project_id: ProjectId,
        user_id: UserId,
        is_primary: bool = False,
        role: str = "viewer",
    ) -> None:
        raise NotImplementedError

    async def remove_user(self, project_id: ProjectId, user_id: UserId) -> None:
        raise NotImplementedError


class ProjectDataCleanup(ABC):
    @abstractmethod
    async def delete_for_project(self, project_id: ProjectId) -> None: ...


class UserDirectory(ABC):
    @abstractmethod
    async def exists(self, user_id: UserId) -> bool: ...


class ProjectNotificationPort(ABC):
    @abstractmethod
    async def publish_warning(
        self, project_id: ProjectId, project_name: str
    ) -> None: ...
