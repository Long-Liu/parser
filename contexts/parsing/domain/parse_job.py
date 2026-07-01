from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contexts.shared.domain.base_aggregate_root import AggregateRoot
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


class SheetResult:
    """Entity within ParseJob aggregate."""

    def __init__(
        self,
        sheet_name: str,
        template_id: TemplateId | None = None,
        match_status: MatchStatus = MatchStatus.SKIPPED,
    ) -> None:
        self.sheet_name = sheet_name
        self.template_id = template_id
        self.match_status = match_status
        self.total_rows: int = 0
        self.success_rows: int = 0
        self.error_rows: int = 0
        self.errors: list[RowError] = []
        self.extracted_rows: list[ParsedRow] = []


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
        job = cls(job_id, project_id, year_month, file_info, batch_no, uploaded_by)
        job.record(ParseJobSubmitted(
            aggregate_id=job_id.value if job_id else None,
            project_id=project_id.value,
            file_name=file_info.filename,
        ))
        return job

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
            sr.template_id = TemplateId(template_id)
            sr.match_status = MatchStatus.MATCHED
            self.record(SheetMatched(
                aggregate_id=self.id.value,
                sheet_name=sheet_name,
                template_id=template_id,
            ))
        else:
            sr.match_status = MatchStatus.SKIPPED
            self.record(SheetSkipped(
                aggregate_id=self.id.value,
                sheet_name=sheet_name,
            ))
        return sr

    def set_extracted(self, sheet_name: str, rows: list[ParsedRow]) -> None:
        if self.id is None:
            raise RuntimeError("ParseJob must be persisted before recording extraction")
        sr = self._sheets[sheet_name]
        sr.extracted_rows = rows
        sr.total_rows = len(rows)
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
        sr.extracted_rows = valid_rows
        sr.errors = errors
        sr.success_rows = len(valid_rows)
        sr.error_rows = len(errors)
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
    def overall_status(self) -> str:
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
