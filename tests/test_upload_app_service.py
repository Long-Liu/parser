import contextlib

import pytest
import tortoise.transactions

from contexts.parsing.application.dto import UploadedFile
from contexts.parsing.application.file_storage import FileStorage, StoredFile
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.parsing.domain.data_sink import ParsedDataSink
from contexts.parsing.domain.parse_job import ParseJob
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.parsing.domain.workbook import WorkbookReader, WorkbookSheet
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository
from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.template.domain.repositories import TemplateCatalog
from contexts.template.domain.template import (
    ColumnMapping,
    HeaderSpec,
    StopRule,
    StopRuleType,
    Template,
)


class FakeRepo(ParseJobRepository):
    def __init__(self) -> None:
        self.jobs: list[ParseJob] = []
        self.status = None

    async def save(self, job: ParseJob) -> None:
        if job.id is None:
            job.id = JobId(1)
        self.jobs.append(job)

    async def find_by_id(self, job_id: JobId) -> ParseJob | None:
        return self.jobs[-1] if self.jobs else None

    async def find_by_project(
        self, project_id: ProjectId, limit: int = 20, offset: int = 0
    ) -> list[ParseJob]:
        return []

    async def list_recent(self, limit: int = 100, offset: int = 0) -> list[ParseJob]:
        return []

    async def count(self, project_id=None) -> int:
        return len(self.jobs)


class FakeTemplateCatalog(TemplateCatalog):
    async def find_by_id(self, template_id: TemplateId) -> Template | None:
        return None

    async def find_all_active(self) -> list[Template]:
        return []

    async def find_matching(self, sheet_name: str) -> Template | None:
        return Template(
            template_id=TemplateId("labor_cost"),
            sheet_pattern="Sheet1",
            header_spec=HeaderSpec(header_rows=[0], data_start_row=2),
            stop_rules=[
                StopRule(
                    rule_type=StopRuleType.CONSECUTIVE_EMPTY,
                    empty_row_count=1,
                )
            ],
            fixed_columns=[
                ColumnMapping(
                    db_field="amount", match_headers=["Amount"], db_type="decimal"
                )
            ],
        )


class FakeSink(ParsedDataSink):
    def __init__(self) -> None:
        self.rows = []

    async def insert_data_rows(self, template_id: str, batch_id: int, rows) -> None:
        self.rows.extend(rows)


class FakeStorage(FileStorage):
    async def save(self, filename: str, body: bytes) -> StoredFile:
        return StoredFile(path="ignored.xlsx", size=len(body))

    async def delete(self, stored_file: StoredFile) -> None:
        return None


class FakeWorkbookReader(WorkbookReader):
    async def read(self, filepath: str) -> list[WorkbookSheet]:
        return [
            WorkbookSheet(
                name="Sheet1",
                grid=[["Amount"], [1], [None]],
                merged_ranges=[],
            )
        ]


class FakePublisher(EventPublisher):
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        self.events.extend(events)


class FakePreviewRepo:
    def __init__(self):
        self.data = None

    async def save(self, batch_id, payload, summary):
        self.data = {"payload": payload, "summary": summary}

    async def get(self, batch_id):
        return self.data

    async def delete(self, batch_id):
        self.data = None

    async def cleanup_expired(self, max_age_hours=24):
        return 0


class FakeProjectRepo(ProjectRepository):
    async def save(self, project: Project) -> None:
        return None

    async def find_by_id(self, project_id: ProjectId) -> Project | None:
        return Project(project_id, "P001", "Test")

    async def find_by_code(self, code: str) -> Project | None:
        return None

    async def list_all(self, *, keyword: str = "", status: str = "",
                       offset: int = 0, limit: int = 20) -> tuple[list[Project], int]:
        return [], 0


async def test_upload_process_records_extracted_event_and_counts(monkeypatch):
    @contextlib.asynccontextmanager
    async def fake_transaction(connection_name=None):
        yield object()

    monkeypatch.setattr(tortoise.transactions, "in_transaction", fake_transaction)

    repo = FakeRepo()
    sink = FakeSink()
    publisher = FakePublisher()
    service = UploadApplicationService(
        repo=repo,
        template_repo=FakeTemplateCatalog(),
        data_sink=sink,
        event_publisher=publisher,
        file_storage=FakeStorage(),
        workbook_reader=FakeWorkbookReader(),
        project_repo=FakeProjectRepo(),
    )

    result = await service.process(
        UploadedFile(name="cost.xlsx", body=b"xlsx"),
        ProjectId(1),
        YearMonth.parse("2026-07"),
        UserId(1),
    )

    assert result["status"] == "success"
    assert result["sheets"][0]["rows"] == 1
    assert len(sink.rows) == 1
    assert any(type(event).__name__ == "SheetExtracted" for event in publisher.events)
    assert repo.jobs[-1].sheets[0].total_rows == 1


async def test_upload_rejects_unknown_project_before_storing_file():
    class MissingProjectRepo(FakeProjectRepo):
        async def find_by_id(self, project_id: ProjectId) -> Project | None:
            return None

    class TrackingStorage(FakeStorage):
        def __init__(self) -> None:
            self.saved = False

        async def save(self, filename: str, body: bytes) -> StoredFile:
            self.saved = True
            return await super().save(filename, body)

    storage = TrackingStorage()
    service = UploadApplicationService(
        repo=FakeRepo(),
        template_repo=FakeTemplateCatalog(),
        data_sink=FakeSink(),
        event_publisher=FakePublisher(),
        file_storage=storage,
        workbook_reader=FakeWorkbookReader(),
        project_repo=MissingProjectRepo(),
    )

    with pytest.raises(NotFoundError, match="project 999"):
        await service.process(
            UploadedFile(name="cost.xlsx", body=b"xlsx"),
            ProjectId(999),
            YearMonth.parse("2026-07"),
            UserId(1),
        )

    assert storage.saved is False


async def test_upload_preview_does_not_write_until_confirmed(monkeypatch):
    @contextlib.asynccontextmanager
    async def fake_transaction(connection_name=None):
        yield object()

    monkeypatch.setattr(tortoise.transactions, "in_transaction", fake_transaction)
    repo = FakeRepo()
    preview_repo = FakePreviewRepo()
    sink = FakeSink()
    service = UploadApplicationService(
        repo=repo, template_repo=FakeTemplateCatalog(), data_sink=sink,
        event_publisher=FakePublisher(), file_storage=FakeStorage(),
        workbook_reader=FakeWorkbookReader(), project_repo=FakeProjectRepo(),
        preview_repo=preview_repo,
    )
    preview = await service.preview(
        UploadedFile(name="cost.xlsx", body=b"xlsx"), ProjectId(1),
        YearMonth.parse("2026-07"), UserId(1),
    )
    assert preview["status"] == "preview"
    assert preview["sheets"][0]["preview"] == [{"amount": 1}]
    assert sink.rows == []

    confirmed = await UploadApplicationService.confirm.__wrapped__(
        service, preview["batch_id"], UserId(1),
    )
    assert confirmed["status"] == "success"
    assert len(sink.rows) == 1
    assert preview_repo.data is None
