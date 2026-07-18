from __future__ import annotations

import json

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.alert.application.constants import ALL_PROJECTS
from contexts.alert.infrastructure.push import AlertWebSocketHub
from contexts.auth.application.authorization_app_service import AuthorizationApplicationService
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.shared.domain.exceptions import AuthenticationError
from contexts.shared.domain.identifiers import UserId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from


class AlertController(BaseController):
    name = "alerts"

    def __init__(self, alert_svc: AlertApplicationService,
                 access_policy: ProjectAccessPolicy,
                 authorization_svc: AuthorizationApplicationService,
                 websocket_hub: AlertWebSocketHub) -> None:
        super().__init__()
        self.alert_svc = alert_svc
        self.access = access_policy
        self.authorization = authorization_svc
        self.hub = websocket_hub

    def setup(self):
        self.bp.add_route(self.list_alerts, "/alerts", methods=["GET"])
        self.bp.add_route(self.summary, "/alerts/summary", methods=["GET"])
        self.bp.add_route(self.rules, "/alert-rules", methods=["GET"])
        self.bp.add_route(self.update_rule, "/alert-rules/<rule_id:int>", methods=["PUT"])
        self.bp.add_route(self.get_alert, "/alerts/<alert_id:int>", methods=["GET"])
        self.bp.add_route(self.events, "/alerts/<alert_id:int>/events", methods=["GET"])
        self.bp.add_route(self.acknowledge, "/alerts/<alert_id:int>/acknowledge", methods=["PUT"])
        self.bp.add_route(self.resolve, "/alerts/<alert_id:int>/resolve", methods=["PUT"])
        self.bp.add_route(self.ignore, "/alerts/<alert_id:int>/ignore", methods=["PUT"])
        self.bp.add_route(self.evaluate, "/alerts/evaluate/<project_id:int>", methods=["POST"])
        self.bp.add_websocket_route(self.stream, "/ws/alerts")

    async def _scope(self, request) -> list[int] | None:
        permissions = set(request.ctx.permissions or set())
        if ProjectAccessPolicy.has_elevated_permission(permissions):
            return None
        return await self.access.accessible_project_ids(UserId(request.ctx.user_id))

    async def _authorize_alert(self, request, alert_id: int,
                               manager: bool = False) -> None:
        project_id = await self.alert_svc.project_id(alert_id)
        permissions = set(request.ctx.permissions or set())
        if ProjectAccessPolicy.has_elevated_permission(permissions):
            return
        await self.access.require(
            UserId(request.ctx.user_id), project_id,
            {"manager"} if manager else None,
        )

    @require_auth
    @require_permission("data:view")
    async def list_alerts(self, request):
        return self.json(await self.alert_svc.find(
            project_ids=await self._scope(request),
            status=request.args.get("status", ""),
            level=request.args.get("level", ""),
            pagination=pagination_from(request),
        ))

    @require_auth
    @require_permission("data:view")
    async def summary(self, request):
        return self.json(await self.alert_svc.summary(await self._scope(request)))

    @require_auth
    @require_permission("admin:roles")
    async def rules(self, request):
        return self.json(await self.alert_svc.rules(pagination_from(request)))

    @require_auth
    @require_permission("admin:roles")
    async def update_rule(self, request, rule_id: int):
        return self.json(await self.alert_svc.update_rule(rule_id, request.json or {}))

    @require_auth
    @require_permission("data:view")
    async def get_alert(self, request, alert_id: int):
        await self._authorize_alert(request, alert_id)
        return self.json(await self.alert_svc.get(alert_id))

    @require_auth
    @require_permission("data:view")
    async def events(self, request, alert_id: int):
        await self._authorize_alert(request, alert_id)
        return self.json(await self.alert_svc.events(alert_id, pagination_from(request)))

    @require_auth
    @require_permission("data:view")
    async def acknowledge(self, request, alert_id: int):
        await self._authorize_alert(request, alert_id)
        body = request.json or {}
        return self.json(await self.alert_svc.acknowledge(
            alert_id, request.ctx.user_id, body.get("note", "")))

    @require_auth
    @require_permission("data:delete")
    async def resolve(self, request, alert_id: int):
        await self._authorize_alert(request, alert_id, manager=True)
        return self.json(await self.alert_svc.resolve(
            alert_id, request.ctx.user_id, (request.json or {}).get("note", "")))

    @require_auth
    @require_permission("data:delete")
    async def ignore(self, request, alert_id: int):
        await self._authorize_alert(request, alert_id, manager=True)
        return self.json(await self.alert_svc.ignore(
            alert_id, request.ctx.user_id, (request.json or {}).get("note", "")))

    @require_auth
    @require_permission("data:upload")
    async def evaluate(self, request, project_id: int):
        permissions = set(request.ctx.permissions or set())
        if not ProjectAccessPolicy.has_elevated_permission(permissions):
            await self.access.require(UserId(request.ctx.user_id), project_id, {"manager"})
        return self.json(await self.alert_svc.evaluate(
            project_id, (request.json or {}).get("ym")))

    async def stream(self, request, ws):
        token = request.args.get("token", "")
        if not token:
            try:
                auth_message = json.loads(await ws.recv())
                token = auth_message.get("token", "")
            except (TypeError, ValueError, json.JSONDecodeError):
                await ws.close(code=4001, reason="authentication required")
                return
        try:
            context = await self.authorization.authenticate(token)
        except AuthenticationError:
            await ws.close(code=4001, reason="unauthorized")
            return
        if ProjectAccessPolicy.has_elevated_permission(context.permissions):
            projects = [ALL_PROJECTS]
        else:
            projects = await self.access.accessible_project_ids(UserId(context.user_id))
        await self.hub.connect(context.user_id, ws, projects)
        try:
            await ws.send('{"event":"alerts.connected"}')
            # Push missed notifications since reconnect
            since = request.args.get("since")
            missed = await self.alert_svc.missed_notifications(projects, since)
            for entry in missed:
                await ws.send(json.dumps(entry, ensure_ascii=False))
            while True:
                message = await ws.recv()
                if message is None:
                    break
        finally:
            await self.hub.disconnect(context.user_id, ws)
