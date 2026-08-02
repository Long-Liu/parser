"""Notification endpoints — owned by the auth context (user-facing concern).

Routes moved verbatim from the analytics controller; the URL space is
unchanged (``/api/notifications``) so no client breaks.
"""

from __future__ import annotations

from sanic_ext import openapi

from contexts.auth.application.notification_app_service import NotificationApplicationService
from contexts.auth.application.project_access import (
    ProjectAccessPolicy,
    resolve_project_scope,
)
from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.auth.interface.request_context import current_auth
from contexts.shared.domain.identifiers import UserId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from


class NotificationController(BaseController):
    name = "notifications"

    def __init__(self, notification_svc: NotificationApplicationService, access_policy: ProjectAccessPolicy):
        super().__init__()
        self.notification_svc = notification_svc
        self.access_policy = access_policy

    async def _project_scope(self, request) -> list[int] | None:
        auth = current_auth(request)
        return await resolve_project_scope(
            self.access_policy,
            UserId(auth.user_id),
            set(auth.permissions),
        )

    def setup(self):
        r = self.bp.add_route
        r(self.notifications, "/notifications", methods=["GET"])
        r(self.create_notification, "/notifications", methods=["POST"])
        r(self.mark_read, "/notifications/<notification_id:int>/read", methods=["PUT"])
        r(self.mark_all_read, "/notifications/read-all", methods=["POST"])
        r(self.delete_notification, "/notifications/<notification_id:int>", methods=["DELETE"])
        r(self.clear_notifications, "/notifications", methods=["DELETE"])

    @require_auth
    @openapi.tag("Notifications")
    @openapi.summary("List notifications")
    async def notifications(self, request):
        p = pagination_from(request)
        return self.json(
            await self.notification_svc.notifications(
                current_auth(request).user_id,
                p,
                request.args.get("unread_only", "false").lower() == "true",
                await self._project_scope(request),
            )
        )

    @require_auth
    @require_permission("user:manage")
    @openapi.tag("Notifications")
    @openapi.summary("Create notification (admin)")
    async def create_notification(self, request):
        return self.json(await self.notification_svc.create_notification(request.json or {}), status=201)

    @require_auth
    @openapi.tag("Notifications")
    @openapi.summary("Mark notification read")
    async def mark_read(self, request, notification_id: int):
        await self.notification_svc.mark_notification_read(current_auth(request).user_id, notification_id)
        return self.json_ok()

    @require_auth
    @openapi.tag("Notifications")
    @openapi.summary("Mark all notifications read")
    async def mark_all_read(self, request):
        marked = await self.notification_svc.mark_all_notifications_read(current_auth(request).user_id)
        return self.json({"ok": True, "marked": marked})

    @require_auth
    @openapi.tag("Notifications")
    @openapi.summary("Delete own notification")
    async def delete_notification(self, request, notification_id: int):
        await self.notification_svc.delete_notification(current_auth(request).user_id, notification_id)
        return self.json_ok()

    @require_auth
    @openapi.tag("Notifications")
    @openapi.summary("Clear own notifications")
    async def clear_notifications(self, request):
        deleted = await self.notification_svc.clear_notifications(current_auth(request).user_id)
        return self.json({"ok": True, "deleted": deleted})
