from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contexts.parsing.domain.events import (
    ParseJobCompleted,
    ParseJobConfirmed,
    ParseJobFailed,
    ParseJobSubmitted,
    SheetExtracted,
    SheetMatched,
    SheetSkipped,
    SheetValidated,
)
from contexts.parsing.domain.year_month import YearMonth
from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_entity import Entity
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId


class JobStatus(StrEnum):
    SUBMITTED = "submitted"
    DONE = "done"
    FAILED = "failed"


class MatchStatus(StrEnum):
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


class SheetResult(Entity[str]):
    """Entity within ParseJob aggregate — tracks one sheet's processing outcome."""

    def __init__(
        self,
        sheet_name: str,
        template_id: TemplateId | None = None,
        match_status: MatchStatus = MatchStatus.SKIPPED,
        total_rows: int = 0,
        success_rows: int = 0,
        error_rows: int = 0,
    ) -> None:
        self.id = sheet_name  # Natural key within the aggregate
        self._template_id = template_id
        self._match_status = match_status
        self._total_rows: int = total_rows
        self._success_rows: int = success_rows
        self._error_rows: int = error_rows
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


class ParseJob(AggregateRoot[JobId]):
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
        self._is_preview = False

    @property
    def sheets(self) -> list[SheetResult]:
        return list(self._sheets.values())

    # -- factory --

    @classmethod
    def submit(
        cls,
        job_id: JobId | None,
        project_id: ProjectId,
        year_month: YearMonth,
        file_info: FileInfo,
        batch_no: str = "",
        uploaded_by: UserId | None = None,
    ) -> ParseJob:
        """Create a new ParseJob. The ParseJobSubmitted event is deferred until
        confirm_submitted() is called after initial persistence."""
        return cls(job_id, project_id, year_month, file_info, batch_no, uploaded_by)

    @classmethod
    def reconstitute(
        cls,
        job_id: JobId,
        project_id: ProjectId,
        year_month: YearMonth,
        file_info: FileInfo,
        status: str,
        sheets: list[SheetResult],
        batch_no: str = "",
        uploaded_by: UserId | None = None,
    ) -> ParseJob:
        """Reconstitute a ParseJob from persisted state — for repository use only.
        Bypasses event recording since this is not a new operation."""
        job = cls(job_id, project_id, year_month, file_info, batch_no, uploaded_by)
        # Map persisted status string to JobStatus, handling terminal states from the PR
        _status_map = {
            "submitted": JobStatus.SUBMITTED,
            "failed": JobStatus.FAILED,
            "success": JobStatus.DONE,
            "partial": JobStatus.DONE,
            "preview": JobStatus.DONE,
            "cancelled": JobStatus.DONE,
        }
        job.status = _status_map.get(status, JobStatus.SUBMITTED)
        job._sheets = {s.sheet_name: s for s in sheets}
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

    def update_file_info(self, file_info: FileInfo) -> None:
        """Update file metadata after the stored file is saved."""
        self.file_info = file_info

    def mark_as_previewed(self) -> None:
        """Indicate this job was a preview upload — status is informational only.
        Marks the job so complete() records ParseJobCompleted with is_preview=True."""
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before marking previewed")
        self._is_preview = True
        self.status = JobStatus.DONE

    def confirm(self) -> None:
        """Confirm a preview batch — transition from preview to success."""
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before confirming")
        self.status = JobStatus.DONE
        self.record(ParseJobConfirmed(
            aggregate_id=self.id.value,
            project_id=self.project_id.value,
            year_month=str(self.year_month),
        ))

    def cancel(self) -> None:
        """Cancel a preview batch."""
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before cancelling")
        self.status = JobStatus.DONE

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
            year_month=str(self.year_month),
            total_sheets=total_sheets,
            matched_sheets=matched,
            total_rows=total_rows,
            is_preview=self._is_preview,
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
