from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from contexts.alert.domain.repositories import AlertPushDispatcher
from contexts.alert.infrastructure.tables import AlertOutboxModel


class AlertWebSocketHub:
    def __init__(self) -> None:
        self._connections: dict[int, set] = defaultdict(set)
        self._projects: dict[object, set[int]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket, project_ids: list[int]) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)
            self._projects[websocket] = set(project_ids)

    async def disconnect(self, user_id: int, websocket) -> None:
        async with self._lock:
            self._connections[user_id].discard(websocket)
            self._projects.pop(websocket, None)
            if not self._connections[user_id]:
                self._connections.pop(user_id, None)

    async def publish(self, project_id: int, message: dict) -> None:
        stale = []
        for user_id, sockets in list(self._connections.items()):
            for websocket in list(sockets):
                allowed = self._projects.get(websocket, set())
                if project_id not in allowed and -1 not in allowed:
                    continue
                try:
                    await websocket.send(json.dumps(message, ensure_ascii=False))
                except Exception:
                    stale.append((user_id, websocket))
        for user_id, websocket in stale:
            await self.disconnect(user_id, websocket)


class TortoiseAlertOutboxDispatcher(AlertPushDispatcher):
    def __init__(self, hub: AlertWebSocketHub) -> None:
        self._hub = hub
        self._lock = asyncio.Lock()

    async def dispatch_pending(self) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            from tortoise.expressions import Q
            now = datetime.now(timezone.utc)
            rows = await AlertOutboxModel.filter(
                Q(status="pending"),
                Q(next_retry_at__lte=now) | Q(next_retry_at=None),
            ).order_by("id").limit(100)
            for row in rows:
                try:
                    await self._hub.publish(row.project_id, {
                        "event": row.event_type, "event_id": row.id,
                        "data": row.payload,
                    })
                    row.status = "sent"
                    row.sent_at = now
                    row.last_error = None
                except Exception as exc:
                    row.retry_count += 1
                    row.last_error = str(exc)[:1000]
                    row.next_retry_at = now + timedelta(
                        seconds=min(300, 2 ** min(row.retry_count, 8))
                    )
                await row.save()
