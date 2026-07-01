from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import closing
from collections.abc import Callable
from datetime import datetime

import aiofiles
import openpyxl
from sanic.request import File

from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.domain.unit_of_work import UnitOfWork
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.parsing.domain.parse_job import ParseJob, FileInfo
from contexts.parsing.domain.data_writer import ParsedDataSink
from contexts.parsing.domain.pipeline_services import (
    CellUnmerger,
    DataRowExtractor,
    DataValidator,
    HeaderFlattener,
    MergedCellRange,
    ParsingColumnSpec,
    ParsingDynamicColumnSpec,
    ParsingStopRule,
    ParsingTemplateSpec,
)
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.template.domain.repositories import TemplateRepository

logger = logging.getLogger("parser.upload")
UPLOAD_DIR = os.path.abspath(os.environ.get("UPLOAD_DIR", "uploads"))


class UploadApplicationService:
    def __init__(
        self,
        repo: ParseJobRepository,
        template_repo: TemplateRepository,
        data_sink: ParsedDataSink,
        event_publisher: EventPublisher,
        uow_factory: Callable[[], UnitOfWork],
        worksheet_reader: Callable[[object], tuple[list[list], list[MergedCellRange]]],
    ) -> None:
        self._repo = repo
        self._template_repo = template_repo
        self._data_sink = data_sink
        self._event_publisher = event_publisher
        self._uow_factory = uow_factory
        self._worksheet_reader = worksheet_reader
        self._unmerger = CellUnmerger()
        self._flattener = HeaderFlattener()
        self._extractor = DataRowExtractor()
        self._validator = DataValidator()

    async def process(
        self, file: File, project_id: ProjectId, ym: YearMonth, user_id: UserId
    ) -> dict:
        batch_no = self._make_batch_no()
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(file.body)
        file_size = os.path.getsize(filepath)

        job = ParseJob.submit(
            job_id=None,
            project_id=project_id,
            year_month=ym,
            file_info=FileInfo(filename=file.name, size=file_size),
            batch_no=batch_no,
            uploaded_by=user_id,
        )

        try:
            wb = await asyncio.to_thread(
                openpyxl.load_workbook, filepath, data_only=True
            )
            with closing(wb):
                async with self._uow_factory() as uow:
                    await self._repo.save(job)
                    job.stamp_events(job.id.value)
                    sheet_results = []
                    for sheet_name in wb.sheetnames:
                        r = await self._process_sheet(
                            wb[sheet_name], sheet_name, job
                        )
                        sheet_results.append(r)
                    job.complete()
                    await self._repo.save(job)
                    await uow.commit()
                # Publish after commit — handlers see persisted state
                await self._event_publisher.publish(job.pull_events())
                status = job.overall_status
        except asyncio.CancelledError:
            raise
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
            try:
                os.remove(filepath)
            except OSError:
                logger.debug("failed to remove temp file %s", filepath, exc_info=True)

        return {
            "batch_no": batch_no,
            "job_id": job.id.value if job.id else None,
            "status": status,
            "sheets": sheet_results,
        }

    async def _process_sheet(self, ws, sheet_name: str, job: ParseJob) -> dict:
        template = await self._template_repo.find_matching(sheet_name)

        if template is None:
            job.match_sheet(sheet_name, None)
            return {
                "name": sheet_name, "template": None,
                "rows": 0, "status": "skipped",
            }

        template_spec = self._to_parsing_spec(template)
        job.match_sheet(sheet_name, template_spec.template_id)
        grid, merged_ranges = self._worksheet_reader(ws)
        grid = self._unmerger.unmerge(grid, merged_ranges)
        flat_headers = self._flattener.flatten(
            grid, template_spec.header_rows
        )
        rows = self._extractor.extract(grid, flat_headers, template_spec)

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
                    rule_type=rule.rule_type.value,
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
