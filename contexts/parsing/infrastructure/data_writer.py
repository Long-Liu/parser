from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

# noinspection PyPackageRequirements
from tortoise import fields as tortoise_fields

from contexts.parsing.domain.data_sink import ParsedDataSink
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS

logger = logging.getLogger("parser.data_writer")
BULK_CREATE_BATCH_SIZE = 500


# Field maps are read per row during bulk inserts; cache per model class.
_FIELDS_MAP_CACHE: dict[type, dict] = {}


def _model_values(model, values: dict) -> dict:
    """Normalize values according to the destination model field types."""
    fields_map = _FIELDS_MAP_CACHE.get(model)
    if fields_map is None:
        # noinspection PyProtectedMember
        fields_map = model._meta.fields_map
        _FIELDS_MAP_CACHE[model] = fields_map
    normalized = {}
    for key, value in values.items():
        field = fields_map.get(key)
        if field is None:
            continue
        if value is not None and isinstance(field, tortoise_fields.DecimalField):
            # aiomysql converts Python floats through their binary
            # representation. Decimal(str(...)) keeps Excel's displayed
            # decimal value; quantizing before the ORM conversion also makes
            # half-cent/half-unit rounding deterministic.
            quantum = Decimal(1).scaleb(-field.decimal_places)
            try:
                decimal_value = Decimal(str(value))
                if not decimal_value.is_finite():
                    raise ValueError("non-finite decimal value")
                value = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError) as exc:
                # Validation rejects these upstream (see DataValidator), but a
                # non-finite value reaching the writer must not abort the whole
                # batch silently — surface the offending field.
                raise ValueError(f"invalid decimal value {value!r} for field {key}") from exc
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
