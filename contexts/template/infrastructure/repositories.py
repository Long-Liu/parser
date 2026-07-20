from __future__ import annotations

from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.repositories import TemplateCatalog
from contexts.template.domain.template import Template
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader


class YamlTemplateCatalog(TemplateCatalog):
    def __init__(self) -> None:
        self._yaml_loader = YamlTemplateLoader()
        self._cache: dict[str, Template] | None = None  # lazily populated

    def _ensure_cache(self) -> dict[str, Template]:
        if self._cache is None:
            self._cache = {
                str(t.id): t for t in self._yaml_loader.load_all()
            }
        return self._cache

    async def find_by_id(self, template_id: TemplateId) -> Template | None:
        return self._ensure_cache().get(str(template_id))

    async def find_all_active(self) -> list[Template]:
        return [t for t in self._ensure_cache().values() if t.is_active]

    async def find_matching(self, sheet_name: str) -> Template | None:
        for t in self._ensure_cache().values():
            if t.is_active and t.matches_sheet(sheet_name):
                return t
        return None
