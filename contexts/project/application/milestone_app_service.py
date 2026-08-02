"""Milestone application service — project context (project lifecycle data)."""

from __future__ import annotations

from contexts.project.infrastructure.milestone_repository import TortoiseMilestoneRepository
from contexts.shared.domain.pagination import Pagination


class MilestoneApplicationService:
    def __init__(self, repository: TortoiseMilestoneRepository) -> None:
        self._repository = repository

    async def milestones(self, project_id: int, pagination: Pagination) -> dict:
        return await self._repository.milestones(project_id, pagination)

    async def project_progress(self, project_id: int, pagination: Pagination) -> dict:
        return await self._repository.project_progress(project_id, pagination)

    async def create_milestone(self, project_id: int, data: dict) -> dict:
        return await self._repository.create_milestone(project_id, data)

    async def update_milestone(self, project_id: int, milestone_id: int, data: dict) -> dict:
        return await self._repository.update_milestone(project_id, milestone_id, data)

    async def delete_milestone(self, project_id: int, milestone_id: int) -> None:
        return await self._repository.delete_milestone(project_id, milestone_id)
