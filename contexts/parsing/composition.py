"""Parsing bounded-context composition."""

from contexts.parsing.application.file_storage import FileStorage
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.parsing.domain.data_sink import ParsedDataSink
from contexts.parsing.domain.repositories import (
    ParseJobRepository,
    UploadPreviewRepository,
)
from contexts.parsing.domain.workbook import WorkbookReader
from contexts.project.domain.repositories import ProjectRepository
from contexts.shared.application.transaction import TransactionManager
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.template.domain.repositories import TemplateCatalog


def build_upload_service(
    jobs: ParseJobRepository,
    templates: TemplateCatalog,
    sink: ParsedDataSink,
    events: EventPublisher,
    storage: FileStorage,
    workbooks: WorkbookReader,
    projects: ProjectRepository,
    previews: UploadPreviewRepository,
    transactions: TransactionManager,
) -> UploadApplicationService:
    return UploadApplicationService(
        jobs, templates, sink, events, storage, workbooks, projects,
        previews, transactions,
    )
