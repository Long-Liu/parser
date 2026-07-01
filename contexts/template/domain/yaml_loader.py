from __future__ import annotations

import os
import yaml

from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.template import (
    Template, HeaderSpec, HierarchyConfig, StopRule, StopRuleType,
    ColumnMapping, DynamicColumnMapping,
)


class YamlTemplateLoader:
    def __init__(self, config_dir: str | None = None) -> None:
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                      "config", "templates")
        self._config_dir = os.path.abspath(config_dir)

    def load(self, template_id: str) -> Template:
        filepath = os.path.join(self._config_dir, f"{template_id}.yaml")
        resolved = os.path.realpath(filepath)
        if not resolved.startswith(os.path.realpath(self._config_dir)):
            raise ValueError(f"path traversal blocked: {template_id}")
        with open(resolved, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return self._build(data)

    def load_all(self) -> list[Template]:
        templates = []
        if not os.path.isdir(self._config_dir):
            return templates
        for filename in sorted(os.listdir(self._config_dir)):
            if filename.endswith((".yaml", ".yml")):
                tid = filename.rsplit(".", 1)[0]
                templates.append(self.load(tid))
        return templates

    def _build(self, data: dict) -> Template:
        header_rows = data.get("headers", {}).get("rows", [])
        data_start_row = data.get("headers", {}).get("data_start_row", 0)
        hierarchy = None
        if "hierarchy" in data:
            hierarchy = HierarchyConfig(
                column_name=data["hierarchy"]["column_name"],
                separator=data["hierarchy"].get("separator", "."),
            )
        stop_rules = []
        for r in data.get("stop_rules", []):
            rt = StopRuleType(r["type"])
            stop_rules.append(StopRule(
                rule_type=rt, patterns=r.get("patterns", []),
                columns=r.get("columns", []),
                empty_row_count=r.get("count") if rt == StopRuleType.CONSECUTIVE_EMPTY else None,
            ))
        fixed_columns = [
            ColumnMapping(db_field=c["db_field"], match_headers=c["match_header"],
                          db_type=c.get("type", "varchar(255)"))
            for c in data.get("columns", [])
        ]
        dynamic_columns = [
            DynamicColumnMapping(db_prefix=c["db_prefix"], match_headers=c["match_header"],
                                 db_type=c.get("type", "decimal(15,2)"))
            for c in data.get("dynamic_columns", [])
        ]
        return Template(
            template_id=TemplateId(data["template_id"]),
            description=data.get("description", ""),
            sheet_pattern=data.get("sheet_pattern", ""),
            header_spec=HeaderSpec(header_rows=header_rows, data_start_row=data_start_row),
            hierarchy_config=hierarchy, stop_rules=stop_rules,
            fixed_columns=fixed_columns, dynamic_columns=dynamic_columns,
            data_table=data.get("data_table", f"data_{data['template_id']}"),
            is_active=data.get("is_active", True),
        )
