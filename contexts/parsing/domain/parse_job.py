from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_entity import Entity
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.parsing.domain.events import (
    ParseJobSubmitted, ParseJobCompleted, ParseJobFailed,
    SheetMatched, SheetSkipped, SheetExtracted, SheetValidated,
)


class JobStatus(str, Enum):
    SUBMITTED = "submitted"
    DONE = "done"
    FAILED = "failed"


class MatchStatus(str, Enum):
    MATCHED = "matched"
    SKIPPED = "skipped"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class FileInfo(ValueObject):
    filename: str
    size: int
    hash: str = ""


@dataclass(frozen=True)
class RowError(ValueObject):
    row_index: int
    field: str = ""
    value: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ParsedRow(ValueObject):
    row_index: int
    fields: dict = field(default_factory=dict)
    hierarchy_code: str | None = None
    monthly_data: dict | None = None


class SheetResult(Entity):
    """Entity within ParseJob aggregate — tracks one sheet's processing outcome."""

    def __init__(
        self,
        sheet_name: str,
        template_id: TemplateId | None = None,
        match_status: MatchStatus = MatchStatus.SKIPPED,
    ) -> None:
        self.id = sheet_name  # Natural key within the aggregate
        self._template_id = template_id
        self._match_status = match_status
        self._total_rows: int = 0
        self._success_rows: int = 0
        self._error_rows: int = 0
        self._errors: list[RowError] = []
        self._extracted_rows: list[ParsedRow] = []

    # -- read-only properties --

    @property
    def sheet_name(self) -> str:
        return self.id  # type: ignore[return-value]

    @property
    def template_id(self) -> TemplateId | None:
        return self._template_id

    @property
    def match_status(self) -> MatchStatus:
        return self._match_status

    @property
    def total_rows(self) -> int:
        return self._total_rows

    @property
    def success_rows(self) -> int:
        return self._success_rows

    @property
    def error_rows(self) -> int:
        return self._error_rows

    @property
    def errors(self) -> list[RowError]:
        return list(self._errors)

    @property
    def extracted_rows(self) -> list[ParsedRow]:
        return list(self._extracted_rows)

    def _set_counts(self, total: int, success: int, error: int) -> None:
        """Set row counts during rehydration (called by infrastructure layer)."""
        self._total_rows = total
        self._success_rows = success
        self._error_rows = error

    # -- mutations (called by ParseJob aggregate root) --

    def mark_matched(self, template_id: TemplateId) -> None:
        self._template_id = template_id
        self._match_status = MatchStatus.MATCHED

    def mark_skipped(self) -> None:
        self._match_status = MatchStatus.SKIPPED

    def set_extracted(self, rows: list[ParsedRow]) -> None:
        self._extracted_rows = list(rows)
        self._total_rows = len(rows)

    def set_validated(self, valid_rows: list[ParsedRow], errors: list[RowError]) -> None:
        self._extracted_rows = list(valid_rows)
        self._errors = list(errors)
        if self._total_rows == 0:
            self._total_rows = len(valid_rows) + len(errors)
        self._success_rows = len(valid_rows)
        self._error_rows = len(errors)


class ParseJob(AggregateRoot):
    """Root aggregate for an Excel file parsing operation."""

    def __init__(
        self,
        job_id: JobId | None,
        project_id: ProjectId,
        year_month: YearMonth,
        file_info: FileInfo,
        batch_no: str = "",
        uploaded_by: UserId | None = None,
    ) -> None:
        super().__init__()
        self.id = job_id
        self.project_id = project_id
        self.year_month = year_month
        self.file_info = file_info
        self.batch_no = batch_no
        self.uploaded_by = uploaded_by
        self.status = JobStatus.SUBMITTED
        self._sheets: dict[str, SheetResult] = {}

    @property
    def sheets(self) -> list[SheetResult]:
        return list(self._sheets.values())

    # -- factory / rehydration --

    @classmethod
    def submit(
        cls,
        job_id: JobId | None,
        project_id: ProjectId,
        year_month: YearMonth,
        file_info: FileInfo,
        batch_no: str = "",
        uploaded_by: UserId | None = None,
    ) -> "ParseJob":
        """Create a new ParseJob (no events recorded yet — call confirm_submitted after persistence)."""
        return cls(job_id, project_id, year_month, file_info, batch_no, uploaded_by)

    @classmethod
    def rehydrate(
        cls,
        job_id: JobId,
        project_id: ProjectId,
        year_month: YearMonth,
        file_info: FileInfo,
        batch_no: str,
        uploaded_by: UserId | None,
        status: JobStatus,
        sheets: list[SheetResult],
    ) -> "ParseJob":
        job = cls(job_id, project_id, year_month, file_info, batch_no, uploaded_by)
        job.status = status
        job._sheets = {sheet.sheet_name: sheet for sheet in sheets}
        return job

    def confirm_submitted(self) -> None:
        """Record ParseJobSubmitted after persistence has assigned an id."""
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before confirm_submitted")
        self.record(ParseJobSubmitted(
            aggregate_id=self.id.value,
            project_id=self.project_id.value,
            file_name=self.file_info.filename,
        ))

    # -- sheet operations --

    def add_sheet_result(self, sheet_name: str) -> SheetResult:
        sr = SheetResult(sheet_name)
        self._sheets[sheet_name] = sr
        return sr

    def match_sheet(self, sheet_name: str, template_id: str | None) -> SheetResult:
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before processing sheets")
        sr = self._sheets.get(sheet_name)
        if sr is None:
            sr = self.add_sheet_result(sheet_name)
        if template_id:
            sr.mark_matched(TemplateId(template_id))
            self.record(SheetMatched(
                aggregate_id=self.id.value,
                sheet_name=sheet_name,
                template_id=template_id,
            ))
        else:
            sr.mark_skipped()
            self.record(SheetSkipped(
                aggregate_id=self.id.value,
                sheet_name=sheet_name,
            ))
        return sr

    def set_extracted(self, sheet_name: str, rows: list[ParsedRow]) -> None:
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before recording extraction")
        sr = self._sheets[sheet_name]
        sr.set_extracted(rows)
        self.record(SheetExtracted(
            aggregate_id=self.id.value,
            sheet_name=sheet_name,
            row_count=len(rows),
        ))

    def set_validated(
        self, sheet_name: str, valid_rows: list[ParsedRow], errors: list[RowError]
    ) -> None:
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before recording validation")
        sr = self._sheets[sheet_name]
        sr.set_validated(valid_rows, errors)
        self.record(SheetValidated(
            aggregate_id=self.id.value,
            sheet_name=sheet_name,
            valid_count=len(valid_rows),
            error_count=len(errors),
        ))

    def complete(self) -> None:
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before completion")
        self.status = JobStatus.DONE
        total_sheets = len(self._sheets)
        matched = sum(
            1 for s in self._sheets.values()
            if s.match_status == MatchStatus.MATCHED
        )
        total_rows = sum(s.success_rows for s in self._sheets.values())
        self.record(ParseJobCompleted(
            aggregate_id=self.id.value,
            project_id=self.project_id.value,
            total_sheets=total_sheets,
            matched_sheets=matched,
            total_rows=total_rows,
        ))

    def fail(self, reason: str) -> None:
        aggregate_id = self.id.value if self.id else None
        self.status = JobStatus.FAILED
        self.record(ParseJobFailed(
            aggregate_id=aggregate_id,
            reason=reason,
        ))

    @property
    def result_status(self) -> str:
        if self.status == JobStatus.FAILED:
            return "failed"
        successes = [
            s for s in self._sheets.values()
            if s.match_status == MatchStatus.MATCHED
        ]
        if not successes:
            return "skipped"
        if all(s.error_rows == 0 for s in successes):
            return "success"
        return "partial"
