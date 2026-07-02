from __future__ import annotations

import logging

from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.parsing.domain.data_writer import ParsedDataSink
from contexts.parsing.domain.parse_job import ParsedRow

logger = logging.getLogger("parser.data_writer")


class SqlAlchemyParsedDataSink(ParsedDataSink):
    async def insert_data_rows(
        self, template_id: str, batch_id: int, rows: list[ParsedRow]
    ) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            logger.warning(
                "No data table model for template_id=%r — %d rows dropped (batch=%d)",
                template_id, len(rows), batch_id,
            )
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
        if session is None:
            raise RuntimeError("ParsedDataSink.insert_data_rows requires an active UnitOfWork")
        await _insert(session)
