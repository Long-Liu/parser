"""Tests for ParseJob aggregate root and SheetResult entity."""

import pytest
from contexts.parsing.domain.parse_job import (
    ParseJob, SheetResult, FileInfo, ParsedRow, RowError, JobStatus, MatchStatus,
)
from contexts.shared.domain.identifiers import JobId, ProjectId, UserId, TemplateId
from contexts.shared.domain.year_month import YearMonth


def _make_job(job_id: int = 1) -> ParseJob:
    return ParseJob.submit(
        job_id=JobId(job_id),
        project_id=ProjectId(1),
        year_month=YearMonth.parse("2026-07"),
        file_info=FileInfo(filename="cost.xlsx", size=100),
        uploaded_by=UserId(1),
    )


# ── ParseJob lifecycle ──────────────────────────────────────────────

def test_submit_creates_job_with_submitted_status():
    job = _make_job()
    assert job.status == JobStatus.SUBMITTED
    assert job.id == JobId(1)


def test_confirm_submitted_records_event():
    job = _make_job()
    job.confirm_submitted()
    events = job.pull_events()
    assert len(events) == 1
    assert events[0].aggregate_id == 1


def test_confirm_submitted_raises_if_no_id():
    job = ParseJob.submit(
        job_id=None, project_id=ProjectId(1),
        year_month=YearMonth.parse("2026-07"),
        file_info=FileInfo(filename="f.xlsx", size=1),
    )
    with pytest.raises(RuntimeError, match="persisted"):
        job.confirm_submitted()


def test_match_sheet_matched():
    job = _make_job()
    sr = job.match_sheet("Sheet1", "labor_cost")
    assert sr.match_status == MatchStatus.MATCHED
    assert sr.template_id == TemplateId("labor_cost")


def test_match_sheet_skipped():
    job = _make_job()
    sr = job.match_sheet("Unknown", None)
    assert sr.match_status == MatchStatus.SKIPPED
    assert sr.template_id is None


def test_set_extracted_records_sheet_data():
    job = _make_job()
    job.match_sheet("Sheet1", "labor_cost")
    rows = [ParsedRow(row_index=1, fields={"amount": 100})]
    job.set_extracted("Sheet1", rows)
    sr = job.sheets[0]
    assert sr.total_rows == 1
    assert len(sr.extracted_rows) == 1


def test_set_validated_preserves_total_rows():
    job = _make_job()
    job.match_sheet("Sheet1", "labor_cost")
    rows = [
        ParsedRow(row_index=1, fields={"amount": 100}),
        ParsedRow(row_index=2, fields={"amount": "bad"}),
    ]
    job.set_extracted("Sheet1", rows)
    job.set_validated(
        "Sheet1",
        [rows[0]],
        [RowError(row_index=2, field="amount", reason="expected decimal")],
    )
    sr = job.sheets[0]
    assert sr.total_rows == 2
    assert sr.success_rows == 1
    assert sr.error_rows == 1


def test_complete_transitions_to_done_and_records_event():
    job = _make_job()
    job.match_sheet("Sheet1", "labor_cost")
    job.set_extracted("Sheet1", [ParsedRow(row_index=1, fields={"amount": 100})])
    job.set_validated(
        "Sheet1",
        [ParsedRow(row_index=1, fields={"amount": 100})],
        [],
    )
    job.complete()
    assert job.status == JobStatus.DONE
    events = job.pull_events()
    completed = [e for e in events if type(e).__name__ == "ParseJobCompleted"]
    assert len(completed) == 1
    assert completed[0].total_rows == 1


def test_fail_transitions_to_failed():
    job = _make_job()
    job.fail("disk full")
    assert job.status == JobStatus.FAILED
    events = job.pull_events()
    assert events[0].reason == "disk full"


def test_result_status_success():
    job = _make_job()
    job.match_sheet("Sheet1", "t1")
    job.set_extracted("Sheet1", [ParsedRow(row_index=1, fields={"x": 1})])
    job.set_validated("Sheet1", [ParsedRow(row_index=1, fields={"x": 1})], [])
    job.complete()
    assert job.result_status == "success"


def test_result_status_partial():
    job = _make_job()
    job.match_sheet("Sheet1", "t1")
    rows = [ParsedRow(row_index=1, fields={"x": 1}), ParsedRow(row_index=2, fields={"x": "bad"})]
    job.set_extracted("Sheet1", rows)
    job.set_validated("Sheet1", [rows[0]], [RowError(row_index=2, field="x", reason="bad")])
    job.complete()
    assert job.result_status == "partial"


def test_result_status_skipped():
    job = _make_job()
    job.match_sheet("Sheet1", None)  # no template match
    job.complete()
    assert job.result_status == "skipped"


def test_result_status_failed():
    job = _make_job()
    job.fail("boom")
    assert job.result_status == "failed"


# ── SheetResult ──────────────────────────────────────────────────────

def test_sheet_result_initial_state():
    sr = SheetResult("Cost")
    assert sr.sheet_name == "Cost"
    assert sr.match_status == MatchStatus.SKIPPED
    assert sr.template_id is None
    assert sr.total_rows == 0
    assert sr.success_rows == 0
    assert sr.error_rows == 0


def test_sheet_result_mark_matched():
    sr = SheetResult("Cost")
    sr.mark_matched(TemplateId("labor_cost"))
    assert sr.match_status == MatchStatus.MATCHED
    assert sr.template_id == TemplateId("labor_cost")


def test_sheet_result_mark_skipped():
    sr = SheetResult("Cost")
    sr.mark_matched(TemplateId("x"))
    sr.mark_skipped()
    assert sr.match_status == MatchStatus.SKIPPED


def test_sheet_result_set_extracted():
    sr = SheetResult("Cost")
    rows = [ParsedRow(row_index=1, fields={"a": 1}), ParsedRow(row_index=2, fields={"a": 2})]
    sr.set_extracted(rows)
    assert sr.total_rows == 2
    assert len(sr.extracted_rows) == 2


def test_sheet_result_set_validated():
    sr = SheetResult("Cost")
    sr.set_extracted([
        ParsedRow(row_index=1, fields={"a": 1}),
        ParsedRow(row_index=2, fields={"a": "bad"}),
    ])
    valid = [ParsedRow(row_index=1, fields={"a": 1})]
    errors = [RowError(row_index=2, field="a", reason="expected decimal")]
    sr.set_validated(valid, errors)
    assert sr.total_rows == 2
    assert sr.success_rows == 1
    assert sr.error_rows == 1


def test_sheet_result_errors_are_immutable_view():
    sr = SheetResult("Cost")
    sr.set_validated([], [RowError(row_index=1, reason="bad")])
    copy = sr.errors
    copy.append(RowError(row_index=2, reason="another"))
    assert len(sr.errors) == 1  # original unaffected


# ── Rehydration ──────────────────────────────────────────────────────

def test_rehydrate_restores_full_state():
    job = _make_job()
    job.match_sheet("Sheet1", "t1")
    job.set_extracted("Sheet1", [ParsedRow(row_index=1, fields={"x": 1})])
    job.set_validated("Sheet1", [ParsedRow(row_index=1, fields={"x": 1})], [])
    job.complete()

    rehydrated = ParseJob.rehydrate(
        job_id=job.id,  # type: ignore[arg-type]
        project_id=job.project_id,
        year_month=job.year_month,
        file_info=job.file_info,
        batch_no=job.batch_no,
        uploaded_by=job.uploaded_by,
        status=job.status,
        sheets=job.sheets,
    )
    assert rehydrated.status == JobStatus.DONE
    assert len(rehydrated.sheets) == 1
    assert rehydrated.sheets[0].sheet_name == "Sheet1"
    assert rehydrated.sheets[0].success_rows == 1


# ── Entity identity ──────────────────────────────────────────────────

def test_parse_job_equality_by_id():
    a = _make_job(1)
    b = ParseJob.rehydrate(
        JobId(1), ProjectId(9), YearMonth.parse("2025-01"),
        FileInfo(filename="other.xlsx", size=0), "B002", None, JobStatus.DONE, []
    )
    assert a == b  # same id, different fields


def test_parse_job_different_id_not_equal():
    a = _make_job(1)
    b = _make_job(2)
    assert a != b


def test_sheet_result_equality_by_sheet_name():
    a = SheetResult("Cost")
    b = SheetResult("Cost")
    b.mark_matched(TemplateId("x"))
    assert a == b  # same natural key


def test_sheet_result_different_name_not_equal():
    assert SheetResult("Cost") != SheetResult("Budget")
