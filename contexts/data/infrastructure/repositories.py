from __future__ import annotations

from contexts.data.domain.data_query import DataRow, FilterCriterion
from contexts.data.domain.repositories import DataQueryRepository
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
from contexts.shared.domain.exceptions import NotFoundError, ValidationError


class DataQueryRepositoryImpl(DataQueryRepository):
    async def query(
        self,
        template_id: str,
        batch_id: int | None,
        filters: list[FilterCriterion],
        pagination: Pagination,
    ) -> tuple[list[DataRow], int]:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            raise NotFoundError(f"template {template_id} not found")

        qs = model.all()
        if batch_id is not None:
            qs = qs.filter(batch_id=batch_id)
        model_fields = set(model._meta.fields_map)
        for f in filters:
            if f.field not in model_fields:
                raise ValidationError(f"unknown filter field: {f.field}")
            if f.operator == "eq":
                qs = qs.filter(**{f.field: f.value})
            elif f.operator == "like":
                qs = qs.filter(**{f"{f.field}__contains": str(f.value)})
            else:
                raise ValidationError(f"unsupported filter operator: {f.operator}")

        total = await qs.count()
        rows = await qs.limit(pagination.size).offset(pagination.offset).values()
        return [DataRow(fields=dict(row)) for row in rows], total

    async def get_by_id(self, template_id: str, row_id: int) -> DataRow | None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            raise NotFoundError(f"template {template_id} not found")
        row = await model.filter(id=row_id).values()
        return DataRow(fields=dict(row[0])) if row else None

    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            raise NotFoundError(f"template {template_id} not found")
        await model.filter(id=row_id).delete()
