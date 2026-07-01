# ponytail: adapted from services/upload_service.py.

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import closing
from datetime import datetime

import aiofiles
import openpyxl
from sanic.request import File

from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from contexts.parsing.domain.parse_job import ParseJob, FileInfo
from contexts.parsing.domain.pipeline_services import (
    CellUnmerger, HeaderFlattener, DataRowExtractor, DataValidator,
)
from contexts.parsing.infrastructure.repositories import ParseJobRepositoryImpl
from contexts.template.domain.yaml_loader import YamlTemplateLoader

logger = logging.getLogger("parser.upload")
UPLOAD_DIR = os.path.abspath(os.environ.get("UPLOAD_DIR", "uploads"))


class UploadApplicationService:
    def __init__(self) -> None:
        self._unmerger = CellUnmerger()
        self._flattener = HeaderFlattener()
        self._extractor = DataRowExtractor()
        self._validator = DataValidator()
        self._template_loader = YamlTemplateLoader()
        self._repo = ParseJobRepositoryImpl()

    async def process(
        self, file: File, project_id: int, ym: str, user_id: int
    ) -> dict:
        batch_no = self._make_batch_no()
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(file.body)
        file_size = os.path.getsize(filepath)

        job = ParseJob.submit(
            job_id=JobId(0),
            project_id=ProjectId(project_id),
            year_month=YearMonth.parse(ym),
            file_info=FileInfo(filename=file.name, size=file_size),
        )

        try:
            wb = await asyncio.to_thread(
                openpyxl.load_workbook, filepath, data_only=True
            )
            with closing(wb):
                sheet_results = []
                for sheet_name in wb.sheetnames:
                    r = await self._process_sheet(
                        wb[sheet_name], sheet_name, job
                    )
                    sheet_results.append(r)
                job.complete()
                await self._repo.save(job)
                status = job.overall_status
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("upload failed for %s", batch_no)
            job.fail("processing error")
            await self._repo.save(job)
            status = "failed"
            sheet_results = []
        finally:
            try:
                os.remove(filepath)
            except OSError:
                logger.debug("failed to remove temp file %s", filepath, exc_info=True)

        return {
            "batch_no": batch_no,
            "job_id": job.id.value,
            "status": status,
            "sheets": sheet_results,
        }

    async def _process_sheet(self, ws, sheet_name: str, job: ParseJob) -> dict:
        template = None
        for t in self._template_loader.load_all():
            if t.matches_sheet(sheet_name):
                template = t
                break

        if template is None:
            job.match_sheet(sheet_name, None)
            return {
                "name": sheet_name, "template": None,
                "rows": 0, "status": "skipped",
            }

        job.match_sheet(sheet_name, str(template.id))
        grid = self._unmerger.unmerge(ws)
        flat_headers = self._flattener.flatten(
            grid, template.header_spec.header_rows
        )
        rows = self._extractor.extract(grid, flat_headers, template)

        for i, r in enumerate(rows):
            object.__setattr__(r, "row_index", i)

        valid_rows, errors = self._validator.validate(rows, template)
        job.set_validated(sheet_name, valid_rows, errors)

        if valid_rows:
            async with SqlAlchemyUnitOfWork() as uow:
                await self._repo.insert_data_rows(
                    str(template.id), valid_rows
                )
                await uow.commit()

        return {
            "name": sheet_name, "template": str(template.id),
            "rows": len(valid_rows),
            "status": "success" if not errors else "partial",
        }

    def _make_batch_no(self) -> str:
        return f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
