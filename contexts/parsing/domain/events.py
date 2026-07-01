from __future__ import annotations
from dataclasses import dataclass
from contexts.shared.domain.base_domain_event import DomainEvent


@dataclass(frozen=True)
class ParseJobSubmitted(DomainEvent):
    project_id: int | None = None
    file_name: str = ""


@dataclass(frozen=True)
class SheetMatched(DomainEvent):
    sheet_name: str = ""
    template_id: str = ""


@dataclass(frozen=True)
class SheetSkipped(DomainEvent):
    sheet_name: str = ""


@dataclass(frozen=True)
class SheetExtracted(DomainEvent):
    sheet_name: str = ""
    row_count: int = 0


@dataclass(frozen=True)
class SheetValidated(DomainEvent):
    sheet_name: str = ""
    valid_count: int = 0
    error_count: int = 0


@dataclass(frozen=True)
class ParseJobCompleted(DomainEvent):
    project_id: int | None = None
    total_sheets: int = 0
    matched_sheets: int = 0
    total_rows: int = 0


@dataclass(frozen=True)
class ParseJobFailed(DomainEvent):
    reason: str = ""
