"""Structural specs for what the parsing pipeline consumes from a template.

The parsing context must not depend on the template context's aggregate
(``contexts.template.domain.template.Template``). These Protocols describe the
parsing algorithm's needs; the template aggregate satisfies them structurally,
so the composition root passes the template object straight through with no
adapter. Pure value enums live in the shared kernel (``stop_rules``).
"""

from __future__ import annotations

from typing import Protocol

from contexts.shared.domain.stop_rules import StopRuleAction, StopRuleType


class StopRuleSpec(Protocol):
    rule_type: StopRuleType
    patterns: list[str]
    columns: list[str]
    empty_row_count: int | None
    action: StopRuleAction
    label_field: str | None


class HeaderSpec(Protocol):
    header_rows: list[int]
    data_start_row: int


class HierarchyConfig(Protocol):
    column_name: str
    separator: str


class ColumnMapping(Protocol):
    db_field: str
    db_type: str


class DynamicColumnMapping(Protocol):
    db_prefix: str


class TemplateSpec(Protocol):
    header_spec: HeaderSpec
    hierarchy_config: HierarchyConfig | None
    stop_rules: list[StopRuleSpec]
    fixed_columns: list[ColumnMapping]

    def find_column(self, flat_header: str, occurrence: int = 1) -> ColumnMapping | None: ...

    def find_dynamic_column(self, flat_header: str) -> DynamicColumnMapping | None: ...
