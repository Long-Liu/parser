"""Notification read/write repository — auth-context owner of Notification.

Moved here from the analytics context: notifications are a user-facing
concern owned by auth; the analytics context only reports against them.
"""

from __future__ import annotations

# noinspection PyPackageRequirements
from tortoise.expressions import Q, Subquery

from contexts.auth.infrastructure.tables import Notification, NotificationRead
from contexts.shared.application.transaction import (
    NoopTransactionManager,
    TransactionManager,
)
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination


class TortoiseNotificationRepository:
    def __init__(self, transaction_manager: TransactionManager | None = None) -> None:
        self._tx = transaction_manager or NoopTransactionManager()

    @staticmethod
    async def notifications(
        user_id: int,
        pagination: Pagination,
        unread_only: bool = False,
        project_ids: list[int] | None = None,
    ) -> dict:
        query = Notification.filter(Q(user_id=user_id) | Q(user_id=None))
        if project_ids is not None:
            query = query.filter(Q(project_id__in=project_ids) | Q(project_id=None))
        # 已读集合用子查询而非全量拉取 ID 列表（原实现每请求把全部可见通知
        # 与全部已读 ID 拉进内存再做 exclude），通知量增长后不再线性膨胀。
        # 注意：Tortoise 1.1.7 的 __in 不接受未求值的 QuerySet，必须用 Subquery 包装。
        read_subquery = Subquery(
            NotificationRead.filter(user_id=user_id).values_list("notification_id", flat=True)
        )
        unread = await query.exclude(id__in=read_subquery).count()
        if unread_only:
            query = query.exclude(id__in=read_subquery)
        total = unread if unread_only else await query.count()
        rows = await query.order_by("-id").offset(pagination.offset).limit(pagination.size)
        read_ids = (
            set(
                await NotificationRead.filter(user_id=user_id, notification_id__in=[r.id for r in rows]).values_list(
                    "notification_id", flat=True
                )
            )
            if rows
            else set()
        )
        return {
            "notifications": [
                {
                    "id": row.id,
                    "type": row.notification_type,
                    "title": row.title,
                    "message": row.message,
                    "project_id": row.project_id,
                    "is_read": row.id in read_ids,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "unread": unread,
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def create_notification(self, data: dict) -> dict:
        async with self._tx.transaction():
            if not data.get("title") or not data.get("message"):
                raise ValidationError("title and message are required")
            row = await Notification.create(
                user_id=data.get("user_id"),
                notification_type=data.get("type", "system"),
                title=data["title"],
                message=data["message"],
                project_id=data.get("project_id"),
            )
            return {"id": row.id, "title": row.title}

    async def mark_notification_read(self, user_id: int, notification_id: int) -> None:
        async with self._tx.transaction():
            exists = await Notification.filter(id=notification_id).filter(Q(user_id=user_id) | Q(user_id=None)).exists()
            if not exists:
                raise NotFoundError(f"notification {notification_id} not found")
            await NotificationRead.get_or_create(
                notification_id=notification_id,
                user_id=user_id,
            )

    async def mark_all_notifications_read(self, user_id: int) -> int:
        """Mark every notification visible to the user (own + broadcast) as read.

        Returns the number of newly marked notifications (idempotent).
        """
        async with self._tx.transaction():
            all_ids = list(await Notification.filter(Q(user_id=user_id) | Q(user_id=None)).values_list("id", flat=True))
            if not all_ids:
                return 0
            read_ids = set(
                await NotificationRead.filter(
                    user_id=user_id,
                    notification_id__in=all_ids,
                ).values_list("notification_id", flat=True)
            )
            unread = [nid for nid in all_ids if nid not in read_ids]
            if unread:
                await NotificationRead.bulk_create(
                    [NotificationRead(notification_id=nid, user_id=user_id) for nid in unread],
                    ignore_conflicts=True,
                )
            return len(unread)

    async def delete_notification(self, user_id: int, notification_id: int) -> None:
        """Delete one of the user's OWN notifications.

        Broadcast notifications (user_id NULL) and other users' notifications
        are not deletable and surface as NotFoundError.
        """
        async with self._tx.transaction():
            deleted = await Notification.filter(
                id=notification_id,
                user_id=user_id,
            ).delete()
            if not deleted:
                raise NotFoundError(f"notification {notification_id} not found")
            await NotificationRead.filter(
                notification_id=notification_id,
                user_id=user_id,
            ).delete()

    async def clear_notifications(self, user_id: int) -> int:
        """Delete all of the user's OWN notifications; returns deleted count.

        Broadcast notifications (user_id NULL) belong to everyone and are kept.
        """
        async with self._tx.transaction():
            own_ids = list(
                await Notification.filter(
                    user_id=user_id,
                ).values_list("id", flat=True)
            )
            if not own_ids:
                return 0
            await NotificationRead.filter(
                notification_id__in=own_ids,
                user_id=user_id,
            ).delete()
            return await Notification.filter(id__in=own_ids).delete()
