from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_domain_event import DomainEvent


@dataclass(frozen=True)
class ProjectCreated(DomainEvent):
    code: str = ""
    name: str = ""


@dataclass(frozen=True)
class ProjectUpdated(DomainEvent):
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectDeleted(DomainEvent):
    code: str = ""
