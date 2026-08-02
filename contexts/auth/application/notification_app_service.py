"""Notification application service — auth context (user-facing concern)."""

from __future__ import annotations

from contexts.auth.infrastructure.notification_repository import TortoiseNotificationRepository
from contexts.shared.domain.pagination import Pagination


class NotificationApplicationService:
    def __init__(self, repository: TortoiseNotificationRepository) -> None:
        self._repository = repository

    async def notifications(
        self,
        user_id: int,
        pagination: Pagination,
        unread_only: bool = False,
        project_ids: list[int] | None = None,
    ) -> dict:
        return await self._repository.notifications(user_id, pagination, unread_only, project_ids)

    async def create_notification(self, data: dict) -> dict:
        return await self._repository.create_notification(data)

    async def mark_notification_read(self, user_id: int, notification_id: int) -> None:
        return await self._repository.mark_notification_read(user_id, notification_id)

    async def mark_all_notifications_read(self, user_id: int) -> int:
        return await self._repository.mark_all_notifications_read(user_id)

    async def delete_notification(self, user_id: int, notification_id: int) -> None:
        return await self._repository.delete_notification(user_id, notification_id)

    async def clear_notifications(self, user_id: int) -> int:
        return await self._repository.clear_notifications(user_id)
