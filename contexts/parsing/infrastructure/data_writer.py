from __future__ import annotations

import logging

from contexts.parsing.domain.data_sink import ParsedDataSink
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS

logger = logging.getLogger("parser.data_writer")


class TortoiseParsedDataSink(ParsedDataSink):
    async def insert_data_rows(
        self, template_id: str, batch_id: int, rows: list[ParsedRow]
    ) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            logger.warning(
                "No data table model for template_id=%r - %d rows dropped (batch=%d)",
                template_id,
                len(rows),
                batch_id,
            )
            return

        data = []
        model_fields = set(model._meta.fields_map)
        for row in rows:
            d = {"batch_id": batch_id, **row.fields}
            if row.hierarchy_code:
                d["hierarchy_code"] = row.hierarchy_code
            if row.monthly_data:
                d["monthly_data"] = row.monthly_data
            data.append(model(**{k: v for k, v in d.items() if k in model_fields}))
        if not data:
            return

        await model.bulk_create(data)
