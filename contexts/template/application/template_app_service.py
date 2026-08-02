from __future__ import annotations

from typing import Protocol

from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.domain.identifiers import TemplateId
from contexts.shared.domain.pagination import Pagination
from contexts.template.domain.repositories import TemplateCatalog
from contexts.template.domain.template import Template


class TemplateWorkbookBuilder(Protocol):
    """Renders a template's .xlsx skeleton to bytes.

    Implemented by the infrastructure openpyxl builder; injected so the
    application layer does not depend on infrastructure (composition root
    adapts)."""

    def __call__(self, template: Template) -> bytes: ...


class TemplateApplicationService:
    def __init__(self, repo: TemplateCatalog, workbook_builder: TemplateWorkbookBuilder) -> None:
        self._repo = repo
        self._builder = workbook_builder

    async def list_all(self, pagination: Pagination) -> dict:
        templates = await self._repo.find_all_active()
        rows = templates[pagination.offset : pagination.offset + pagination.size]
        return {
            "templates": [
                {
                    "template_id": t.id.value if t.id else None,
                    "description": t.description,
                    "sheet_pattern": t.sheet_pattern,
                    "data_table": t.data_table,
                }
                for t in rows
            ],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": len(templates)},
        }

    async def get_by_id(self, template_id: TemplateId) -> dict:
        t = await self._repo.find_by_id(template_id)
        if not t:
            raise NotFoundError(f"template {template_id} not found")
        return {
            "template_id": t.id.value if t.id else None,
            "description": t.description,
            "data_table": t.data_table,
            "fixed_columns": [c.db_field for c in t.fixed_columns],
            "dynamic_columns": [c.db_prefix for c in t.dynamic_columns],
        }

    async def build_download(self, template_id: TemplateId) -> tuple[bytes, str]:
        """Render the .xlsx skeleton for a template; returns (content, filename)."""
        t = await self._repo.find_by_id(template_id)
        if not t:
            raise NotFoundError(f"template {template_id} not found")
        filename = f"{t.description or template_id}.xlsx"
        return self._builder(t), filename
