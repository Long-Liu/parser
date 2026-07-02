from __future__ import annotations

from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.template import Template
from contexts.template.domain.repositories import TemplateCatalog
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader


class YamlTemplateCatalog(TemplateCatalog):
    def __init__(self) -> None:
        self._yaml_loader = YamlTemplateLoader()

    async def find_by_id(self, template_id: TemplateId) -> Template | None:
        try:
            return self._yaml_loader.load(str(template_id))
        except (FileNotFoundError, ValueError):
            return None

    async def find_all_active(self) -> list[Template]:
        return [t for t in self._yaml_loader.load_all() if t.is_active]

    async def find_matching(self, sheet_name: str) -> Template | None:
        for t in self._yaml_loader.load_all():
            if t.is_active and t.matches_sheet(sheet_name):
                return t
        return None
