from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# noinspection PyPackageRequirements
from tortoise import fields as tortoise_fields

from contexts.parsing.domain.data_sink import ParsedDataSink
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS

logger = logging.getLogger("parser.data_writer")
BULK_CREATE_BATCH_SIZE = 500


def _model_values(model, values: dict) -> dict:
    """Normalize values according to the destination model field types."""
    normalized = {}
    for key, value in values.items():
        # noinspection PyProtectedMember
        field = model._meta.fields_map.get(key)
        if field is None:
            continue
        if value is not None and isinstance(field, tortoise_fields.DecimalField):
            # aiomysql converts Python floats through their binary
            # representation. Decimal(str(...)) keeps Excel's displayed
            # decimal value; quantizing before the ORM conversion also makes
            # half-cent/half-unit rounding deterministic.
            quantum = Decimal(1).scaleb(-field.decimal_places)
            value = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
        normalized[key] = value
    return normalized


class TortoiseParsedDataSink(ParsedDataSink):
    async def insert_data_rows(self, template_id: str, batch_id: int, rows: list[ParsedRow]) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            raise RuntimeError(
                f"No data table model for template_id={template_id!r}; refusing to drop {len(rows)} parsed rows"
            )

        data = []
        for row in rows:
            d: dict[str, Any] = {"batch_id": batch_id, **row.fields}
            if row.hierarchy_code:
                d["hierarchy_code"] = row.hierarchy_code
            if row.monthly_data:
                d["monthly_data"] = row.monthly_data
            data.append(model(**_model_values(model, d)))
        if not data:
            return

        await model.bulk_create(data, batch_size=BULK_CREATE_BATCH_SIZE)
