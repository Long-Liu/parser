from contexts.parsing.domain.parse_job import FileInfo, ParseJob, ParsedRow, RowError
from contexts.shared.domain.identifiers import JobId, ProjectId, UserId
from contexts.shared.domain.year_month import YearMonth


def test_set_extracted_preserves_total_rows_after_validation():
    job = ParseJob.submit(
        job_id=JobId(1),
        project_id=ProjectId(1),
        year_month=YearMonth.parse("2026-07"),
        file_info=FileInfo(filename="cost.xlsx", size=10),
        uploaded_by=UserId(1),
    )
    job.match_sheet("Sheet1", "labor_cost")

    rows = [
        ParsedRow(row_index=1, fields={"amount": 1}),
        ParsedRow(row_index=2, fields={"amount": "bad"}),
    ]
    job.set_extracted("Sheet1", rows)
    job.set_validated(
        "Sheet1",
        [rows[0]],
        [RowError(row_index=2, field="amount", reason="expected decimal")],
    )

    sheet = job.sheets[0]
    assert sheet.total_rows == 2
    assert sheet.success_rows == 1
    assert sheet.error_rows == 1
    assert job.result_status == "partial"

