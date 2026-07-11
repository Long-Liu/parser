from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from contexts.shared.application.transaction import transactional

from contexts.parsing.application.dto import UploadedFile
from contexts.parsing.application.file_storage import FileStorage, StoredFile
from contexts.parsing.domain.cell_unmerger import CellUnmerger
from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.data_sink import ParsedDataSink
from contexts.parsing.domain.data_validator import DataValidator
from contexts.parsing.domain.header_flattener import HeaderFlattener
from contexts.parsing.domain.parse_job import FileInfo, ParsedRow, ParseJob
from contexts.parsing.domain.repositories import (
    ParseJobRepository,
    UploadPreviewRepository,
)
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.parsing.domain.workbook import WorkbookReader, WorkbookSheet
from contexts.project.domain.repositories import ProjectRepository
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.domain.identifiers import JobId, ProjectId, UserId
from contexts.shared.domain.year_month import YearMonth
from contexts.template.domain.repositories import TemplateCatalog
from contexts.alert.application.alert_app_service import AlertApplicationService

logger = logging.getLogger("parser.upload")


class UploadApplicationService:
    def __init__(
        self,
        repo: ParseJobRepository,
        template_repo: TemplateCatalog,
        data_sink: ParsedDataSink,
        event_publisher: EventPublisher,
        file_storage: FileStorage,
        workbook_reader: WorkbookReader,
        project_repo: ProjectRepository,
        preview_repo: UploadPreviewRepository | None = None,
        alert_svc: AlertApplicationService | None = None,
    ) -> None:
        self._repo = repo
        self._template_repo = template_repo
        self._data_sink = data_sink
        self._event_publisher = event_publisher
        self._file_storage = file_storage
        self._workbook_reader = workbook_reader
        self._project_repo = project_repo
        self._preview_repo = preview_repo
        self._alert_svc = alert_svc
        self._unmerger = CellUnmerger()
        self._flattener = HeaderFlattener()
        self._stop_detector = StopDetector()
        self._extractor = DataRowExtractor(self._stop_detector)
        self._validator = DataValidator()

    async def process(
        self, file: UploadedFile, project_id: ProjectId, ym: YearMonth, user_id: UserId
    ) -> dict:
        if await self._project_repo.find_by_id(project_id) is None:
            raise NotFoundError(f"project {project_id.value} not found")
        batch_no = self._make_batch_no()
        stored_file: StoredFile | None = None

        job = ParseJob.submit(
            job_id=None,
            project_id=project_id,
            year_month=ym,
            file_info=FileInfo(filename=file.name, size=len(file.body)),
            batch_no=batch_no,
            uploaded_by=user_id,
        )

        try:
            stored_file = await self._file_storage.save(f"{batch_no}.xlsx", file.body)
            job.file_info = FileInfo(filename=file.name, size=stored_file.size)
            sheet_results = await self._process_workbook(stored_file.path, job)
            await self._event_publisher.publish(job.pull_events())
            if self._alert_svc and job.id:
                await self._alert_svc.evaluate(project_id.value, str(ym))
            status = job.result_status
        except Exception:
            logger.exception("upload failed for %s", batch_no)
            job.fail("processing error")
            try:
                await self._save_failed_job(job)
                await self._event_publisher.publish(job.pull_events())
            except Exception:
                logger.exception("failed to persist error status for %s", batch_no)
            status = "failed"
            sheet_results = []
        finally:
            if stored_file is not None:
                await self._delete_stored_file(stored_file)

        return {
            "batch_no": batch_no,
            "job_id": job.id.value if job.id else None,
            "status": status,
            "sheets": sheet_results,
        }

    @transactional
    async def preview(
        self, file: UploadedFile, project_id: ProjectId, ym: YearMonth, user_id: UserId
    ) -> dict:
        if self._preview_repo is None:
            raise RuntimeError("preview repository is not configured")
        await self._preview_repo.cleanup_expired()
        if await self._project_repo.find_by_id(project_id) is None:
            raise NotFoundError(f"project {project_id.value} not found")
        batch_no = self._make_batch_no()
        stored_file = await self._file_storage.save(f"{batch_no}.xlsx", file.body)
        job = ParseJob.submit(
            None,
            project_id,
            ym,
            FileInfo(filename=file.name, size=stored_file.size),
            batch_no,
            user_id,
        )
        try:
            await self._repo.save(job)
            job.confirm_submitted()
            payload, summary = await self._collect_preview_sheets(job, stored_file.path)
            job.complete()
            job.mark_as_previewed()
            await self._event_publisher.publish(job.pull_events())
            await self._repo.save(job)
            await self._preview_repo.save(job.id.value, payload, summary)
            return {"batch_id": job.id.value, "batch_no": batch_no,
                    "status": "preview", "sheets": summary}
        except Exception:
            logger.exception("preview failed for %s", batch_no)
            job.fail("preview error")
            try:
                await self._repo.save(job)
            except Exception:
                logger.exception("failed to persist error status for %s", batch_no)
            raise
        finally:
            await self._delete_stored_file(stored_file)

    @transactional
    async def confirm(self, batch_id: int, user_id: UserId) -> dict:
        if self._preview_repo is None:
            raise RuntimeError("preview repository is not configured")
        preview = await self._preview_repo.get(batch_id)
        job = await self._repo.find_by_id(JobId(batch_id))
        if preview is None or job is None:
            raise NotFoundError(f"preview batch {batch_id} not found")
        if job.uploaded_by is not None and job.uploaded_by != user_id:
            raise NotFoundError(f"preview batch {batch_id} not found")
        for sheet in preview["payload"]:
            rows = [
                ParsedRow(
                    row_index=row["row_index"],
                    fields=self._restore_types(row["fields"]),
                    hierarchy_code=row.get("hierarchy_code"),
                    monthly_data=self._restore_types(row.get("monthly_data")),
                )
                for row in sheet["rows"]
            ]
            if rows:
                await self._data_sink.insert_data_rows(
                    sheet["template"], batch_id, rows
                )
        job.confirm()
        await self._repo.save(job)
        await self._preview_repo.delete(batch_id)
        if self._alert_svc:
            await self._alert_svc.evaluate(job.project_id.value, str(job.year_month))
        return {"batch_id": batch_id, "status": "success", "sheets": preview["summary"]}

    @transactional
    async def cancel_preview(self, batch_id: int, user_id: UserId) -> None:
        if self._preview_repo is None:
            raise RuntimeError("preview repository is not configured")
        job = await self._repo.find_by_id(JobId(batch_id))
        if job is None or (job.uploaded_by is not None and job.uploaded_by != user_id):
            raise NotFoundError(f"preview batch {batch_id} not found")
        job.cancel()
        await self._repo.save(job)
        await self._preview_repo.delete(batch_id)

    async def _delete_stored_file(self, stored_file: StoredFile) -> None:
        try:
            await self._file_storage.delete(stored_file)
        except Exception:
            logger.warning(
                "failed to remove temp file %s", stored_file.path, exc_info=True
            )

    @transactional
    async def _process_workbook(self, stored_path: str, job: ParseJob) -> list[dict]:
        workbook_sheets = await self._workbook_reader.read(stored_path)
        sheet_results = []
        await self._repo.save(job)
        job.confirm_submitted()
        for sheet in workbook_sheets:
            r = await self._process_sheet(sheet, job)
            sheet_results.append(r)
        job.complete()
        await self._repo.save(job)
        return sheet_results

    @transactional
    async def _save_failed_job(self, job: ParseJob) -> None:
        await self._repo.save(job)

    async def _process_sheet(
        self, sheet: WorkbookSheet, job: ParseJob, write: bool = True
    ) -> dict:
        sheet_name = sheet.name
        template = await self._template_repo.find_matching(sheet_name)

        if template is None:
            job.match_sheet(sheet_name, None)
            return {"name": sheet_name, "template": None, "rows": 0, "status": "skipped"}

        job.match_sheet(sheet_name, template.id.value)
        valid_rows, errors = await self._run_parsing_pipeline(sheet, job, template)

        if valid_rows and write:
            if job.id is None:
                raise RuntimeError("ParseJob repository did not assign an id")
            await self._data_sink.insert_data_rows(
                template.id.value, job.id.value, valid_rows)

        result = {"name": sheet_name, "template": template.id.value,
                  "rows": len(valid_rows),
                  "status": "success" if not errors else "partial"}
        if not write:
            result.update(self._build_preview_data(valid_rows, errors))
        return result

    async def _collect_preview_sheets(self, job, stored_path):
        """Process all sheets without persisting data, collecting preview results."""
        payload, summary = [], []
        for sheet in await self._workbook_reader.read(stored_path):
            result = await self._process_sheet(sheet, job, write=False)
            rows = result.pop("_rows", [])
            summary.append(result)
            if result.get("template"):
                payload.append({"template": result["template"], "rows": rows})
        return payload, summary

    async def _run_parsing_pipeline(self, sheet, job, template):
        grid = self._unmerger.unmerge(sheet.grid, sheet.merged_ranges)
        flat_headers = self._flattener.flatten(grid, template.header_spec.header_rows)
        rows = self._extractor.extract(grid, flat_headers, template)
        job.set_extracted(sheet.name, rows)
        valid_rows, errors = self._validator.validate(rows, template)
        job.set_validated(sheet.name, valid_rows, errors)
        return valid_rows, errors

    def _build_preview_data(self, valid_rows, errors) -> dict:
        return {
            "preview": [self._json_safe(r.fields) for r in valid_rows[:20]],
            "errors": [{"row": e.row_index, "field": e.field,
                         "value": e.value, "reason": e.reason}
                        for e in errors[:20]],
            "_rows": [{"row_index": r.row_index, "fields": self._json_safe(r.fields),
                       "hierarchy_code": r.hierarchy_code,
                       "monthly_data": self._json_safe(r.monthly_data)}
                      for r in valid_rows],
        }

    @classmethod
    def _json_safe(cls, value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        return value

    @classmethod
    def _restore_types(cls, value):
        """Reverse _json_safe: convert isoformat strings back to date/datetime,
        and numeric strings back to Decimal where appropriate.
        Leaves non-string values unchanged."""
        if isinstance(value, dict):
            return {key: cls._restore_types(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._restore_types(item) for item in value]
        if isinstance(value, str):
            # Try date/datetime first (isoformat)
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                pass
            try:
                return date.fromisoformat(value)
            except (ValueError, TypeError):
                pass
            # Try Decimal (numeric string)
            try:
                return Decimal(value)
            except Exception:
                pass
        return value

    def _make_batch_no(self) -> str:
        return f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
