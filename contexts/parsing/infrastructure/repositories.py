# ponytail: stub repository — full batch/log persistence in migration phase.

from __future__ import annotations

from db.engine import get_sessionmaker
from db.models import TEMPLATE_DATA_MODELS
from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.parsing.domain.parse_job import ParseJob, ParsedRow
from contexts.parsing.domain.repositories import ParseJobRepository


class ParseJobRepositoryImpl(ParseJobRepository):
    async def next_id(self) -> JobId:
        return JobId(0)

    async def save(self, job: ParseJob) -> None:
        pass  # ponytail: full batch/log persistence in migration phase

    async def find_by_id(self, job_id: JobId) -> ParseJob | None:
        return None

    async def find_by_project(
        self, project_id: ProjectId, limit: int = 20, offset: int = 0
    ) -> list[ParseJob]:
        return []

    async def insert_data_rows(
        self, template_id: str, rows: list[ParsedRow]
    ) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return
        data = []
        for row in rows:
            d = dict(row.fields)
            if row.hierarchy_code:
                d["hierarchy_code"] = row.hierarchy_code
            if row.monthly_data:
                d["monthly_data"] = row.monthly_data
            data.append(d)
        if not data:
            return

        async def _insert(session):
            session.add_all([model()(**row) for row in data])
            await session.flush()

        session = current_session()
        if session is not None:
            await _insert(session)
        else:
            async with get_sessionmaker().begin() as s:
                await _insert(s)
