from __future__ import annotations

from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.repositories import TemplateRepository


class TemplateApplicationService:
    def __init__(self, repo: TemplateRepository) -> None:
        self._repo = repo

    async def list_all(self) -> list[dict]:
        templates = await self._repo.find_all_active()
        return [{"template_id": str(t.id), "description": t.description,
                 "sheet_pattern": t.sheet_pattern, "data_table": t.data_table}
                for t in templates]

    async def get_by_id(self, template_id: TemplateId) -> dict:
        t = await self._repo.find_by_id(template_id)
        if not t:
            raise NotFoundError(f"template {template_id} not found")
        return {"template_id": str(t.id), "description": t.description,
                "data_table": t.data_table,
                "fixed_columns": [c.db_field for c in t.fixed_columns],
                "dynamic_columns": [c.db_prefix for c in t.dynamic_columns]}
