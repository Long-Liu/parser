from __future__ import annotations

from abc import ABC, abstractmethod

from contexts.shared.domain.base_domain_event import DomainEvent


class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, events: list[DomainEvent]) -> None: ...
