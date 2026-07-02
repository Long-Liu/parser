from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import TemplateId


class StopRuleType(str, Enum):
    CELL_MATCH = "cell_match"
    CONSECUTIVE_EMPTY = "consecutive_empty_rows"


@dataclass(frozen=True)
class StopRule(ValueObject):
    rule_type: StopRuleType
    patterns: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    empty_row_count: int | None = None


@dataclass(frozen=True)
class HeaderSpec(ValueObject):
    header_rows: list[int]
    data_start_row: int


@dataclass(frozen=True)
class HierarchyConfig(ValueObject):
    column_name: str
    separator: str = "."


@dataclass(frozen=True)
class ColumnMapping(ValueObject):
    db_field: str
    match_headers: list[str]
    db_type: str = "varchar(255)"


@dataclass(frozen=True)
class DynamicColumnMapping(ValueObject):
    db_prefix: str
    match_headers: list[str]
    db_type: str = "decimal(15,2)"


class Template(AggregateRoot):
    def __init__(self, template_id: TemplateId, description: str = "",
                 sheet_pattern: str = "", header_spec: HeaderSpec | None = None,
                 hierarchy_config: HierarchyConfig | None = None,
                 stop_rules: list[StopRule] | None = None,
                 fixed_columns: list[ColumnMapping] | None = None,
                 dynamic_columns: list[DynamicColumnMapping] | None = None,
                 data_table: str = "", is_active: bool = True) -> None:
        super().__init__()
        self.id = template_id
        self.description = description
        self.sheet_pattern = sheet_pattern
        self.header_spec = header_spec or HeaderSpec(header_rows=[], data_start_row=0)
        self.hierarchy_config = hierarchy_config
        self.stop_rules: list[StopRule] = stop_rules or []
        self.fixed_columns: list[ColumnMapping] = fixed_columns or []
        self.dynamic_columns: list[DynamicColumnMapping] = dynamic_columns or []
        self.data_table = data_table
        self.is_active = is_active

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def matches_sheet(self, sheet_name: str) -> bool:
        return bool(self.sheet_pattern and fnmatch.fnmatch(sheet_name, self.sheet_pattern))

    def find_column(self, flat_header: str) -> ColumnMapping | None:
        for col in self.fixed_columns:
            if all(kw in flat_header for kw in col.match_headers):
                return col
        return None

    def find_dynamic_column(self, flat_header: str) -> DynamicColumnMapping | None:
        for col in self.dynamic_columns:
            if all(kw in flat_header for kw in col.match_headers):
                return col
        return None
