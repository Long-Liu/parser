from __future__ import annotations
from abc import ABC, abstractmethod

from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.template import Template


class TemplateCatalog(ABC):
    @abstractmethod
    async def find_by_id(self, template_id: TemplateId) -> Template | None: ...
    @abstractmethod
    async def find_all_active(self) -> list[Template]: ...
    @abstractmethod
    async def find_matching(self, sheet_name: str) -> Template | None: ...
