from __future__ import annotations

from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.models import TEMPLATE_DATA_MODELS
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.parsing.domain.data_writer import ParsedDataSink
from contexts.parsing.domain.parse_job import ParsedRow


class SqlAlchemyParsedDataSink(ParsedDataSink):
    async def insert_data_rows(
        self, template_id: str, batch_id: int, rows: list[ParsedRow]
    ) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return
        data = []
        for row in rows:
            d = {"batch_id": batch_id, **row.fields}
            if row.hierarchy_code:
                d["hierarchy_code"] = row.hierarchy_code
            if row.monthly_data:
                d["monthly_data"] = row.monthly_data
            data.append(d)
        if not data:
            return

        async def _insert(session):
            session.add_all([model(**row) for row in data])
            await session.flush()

        session = current_session()
        if session is not None:
            await _insert(session)
        else:
            async with get_sessionmaker().begin() as s:
                await _insert(s)
