from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime

from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.domain.unit_of_work import UnitOfWork
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.parsing.domain.parse_job import ParseJob, FileInfo
from contexts.parsing.domain.data_writer import ParsedDataSink
from contexts.parsing.domain.workbook import WorkbookReader, WorkbookSheet
from contexts.parsing.application.dto import UploadedFile
from contexts.parsing.application.file_storage import FileStorage, StoredFile
from contexts.parsing.domain.pipeline_services import (
    CellUnmerger,
    DataRowExtractor,
    DataValidator,
    HeaderFlattener,
    ParsingColumnSpec,
    ParsingDynamicColumnSpec,
    ParsingStopRule,
    ParsingStopRuleType,
    ParsingTemplateSpec,
)
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.template.domain.repositories import TemplateCatalog

logger = logging.getLogger("parser.upload")


class UploadApplicationService:
    def __init__(
        self,
        repo: ParseJobRepository,
        template_repo: TemplateCatalog,
        data_sink: ParsedDataSink,
        event_publisher: EventPublisher,
        uow_factory: Callable[[], UnitOfWork],
        file_storage: FileStorage,
        workbook_reader: WorkbookReader,
    ) -> None:
        self._repo = repo
        self._template_repo = template_repo
        self._data_sink = data_sink
        self._event_publisher = event_publisher
        self._uow_factory = uow_factory
        self._file_storage = file_storage
        self._workbook_reader = workbook_reader
        self._unmerger = CellUnmerger()
        self._flattener = HeaderFlattener()
        self._extractor = DataRowExtractor()
        self._validator = DataValidator()

    async def process(
        self, file: UploadedFile, project_id: ProjectId, ym: YearMonth, user_id: UserId
    ) -> dict:
        batch_no = self._make_batch_no()
        stored_file = await self._file_storage.save(f"{batch_no}.xlsx", file.body)

        job = ParseJob.submit(
            job_id=None,
            project_id=project_id,
            year_month=ym,
            file_info=FileInfo(filename=file.name, size=stored_file.size),
            batch_no=batch_no,
            uploaded_by=user_id,
        )

        try:
            workbook_sheets = await self._workbook_reader.read(stored_file.path)
            async with self._uow_factory() as uow:
                await self._repo.save(job)
                job.stamp_events(job.id.value)
                sheet_results = []
                for sheet in workbook_sheets:
                    r = await self._process_sheet(sheet, job)
                    sheet_results.append(r)
                job.complete()
                await self._repo.save(job)
                await uow.commit()
            await self._event_publisher.publish(job.pull_events())
            status = job.result_status
        except Exception:
            logger.exception("upload failed for %s", batch_no)
            job.fail("processing error")
            async with self._uow_factory() as uow:
                await self._repo.save(job)
                if job.id is not None:
                    job.stamp_events(job.id.value)
                await uow.commit()
            await self._event_publisher.publish(job.pull_events())
            status = "failed"
            sheet_results = []
        finally:
            await self._delete_stored_file(stored_file)

        return {
            "batch_no": batch_no,
            "job_id": job.id.value if job.id else None,
            "status": status,
            "sheets": sheet_results,
        }

    async def _delete_stored_file(self, stored_file: StoredFile) -> None:
        try:
            await self._file_storage.delete(stored_file)
        except Exception:
            logger.debug(
                "failed to remove temp file %s", stored_file.path, exc_info=True
            )

    async def _process_sheet(self, sheet: WorkbookSheet, job: ParseJob) -> dict:
        sheet_name = sheet.name
        template = await self._template_repo.find_matching(sheet_name)

        if template is None:
            job.match_sheet(sheet_name, None)
            return {
                "name": sheet_name, "template": None,
                "rows": 0, "status": "skipped",
            }

        template_spec = self._to_parsing_spec(template)
        job.match_sheet(sheet_name, template_spec.template_id)
        grid = self._unmerger.unmerge(sheet.grid, sheet.merged_ranges)
        flat_headers = self._flattener.flatten(
            grid, template_spec.header_rows
        )
        rows = self._extractor.extract(grid, flat_headers, template_spec)
        job.set_extracted(sheet_name, rows)

        valid_rows, errors = self._validator.validate(rows, template_spec)
        job.set_validated(sheet_name, valid_rows, errors)

        if valid_rows:
            if job.id is None:
                raise RuntimeError("ParseJob repository did not assign an id")
            await self._data_sink.insert_data_rows(
                template_spec.template_id, job.id.value, valid_rows
            )

        return {
            "name": sheet_name, "template": template_spec.template_id,
            "rows": len(valid_rows),
            "status": "success" if not errors else "partial",
        }

    def _make_batch_no(self) -> str:
        return f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    def _to_parsing_spec(self, template) -> ParsingTemplateSpec:
        return ParsingTemplateSpec(
            template_id=str(template.id),
            header_rows=template.header_spec.header_rows,
            data_start_row=template.header_spec.data_start_row,
            stop_rules=[
                ParsingStopRule(
                    rule_type=ParsingStopRuleType(rule.rule_type.value),
                    patterns=rule.patterns,
                    columns=rule.columns,
                    empty_row_count=rule.empty_row_count,
                )
                for rule in template.stop_rules
            ],
            fixed_columns=[
                ParsingColumnSpec(
                    db_field=column.db_field,
                    match_headers=column.match_headers,
                    db_type=column.db_type,
                )
                for column in template.fixed_columns
            ],
            dynamic_columns=[
                ParsingDynamicColumnSpec(
                    db_prefix=column.db_prefix,
                    match_headers=column.match_headers,
                    db_type=column.db_type,
                )
                for column in template.dynamic_columns
            ],
        )
