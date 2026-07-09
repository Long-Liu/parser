import pytest
import tempfile
import os
import re

from tortoise import fields

from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
from contexts.template.infrastructure.config_loader import (
    load_config,
    list_configs,
)
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader


DECIMAL_RE = re.compile(r"^decimal\((\d+),\s*(\d+)\)$", re.IGNORECASE)


@pytest.fixture
def config_dir():
    with tempfile.TemporaryDirectory() as d:
        yaml_content = """
template_id: test_tpl
sheet_pattern: "表1*人工费*"
description: "测试模板"
headers:
  rows: [2, 3, 4]
  data_start_row: 5
columns:
  - db_field: "name"
    match_header: ["姓名"]
    type: "varchar(100)"
stop_rules:
  - type: cell_match
    patterns: ["^注："]
    columns: ["A"]
"""
        with open(os.path.join(d, "test_tpl.yaml"), "w", encoding="utf-8") as f:
            f.write(yaml_content)
        yield d


def test_load_config(config_dir):
    config = load_config("test_tpl", config_dir=config_dir)
    assert config["template_id"] == "test_tpl"
    assert config["headers"]["data_start_row"] == 5
    assert len(config["columns"]) == 1


def test_list_configs(config_dir):
    configs = list_configs(config_dir=config_dir)
    assert len(configs) == 1
    assert configs[0]["template_id"] == "test_tpl"


def test_yaml_loader_matches_sheet(config_dir):
    loader = YamlTemplateLoader(config_dir=config_dir)
    templates = loader.load_all()
    assert len(templates) == 1
    assert templates[0].matches_sheet("表1 人工费-动态") is True


def test_yaml_loader_no_match(config_dir):
    loader = YamlTemplateLoader(config_dir=config_dir)
    templates = loader.load_all()
    assert templates[0].matches_sheet("不存在的Sheet名") is False


def test_all_template_configs_match_data_tables():
    configs = list_configs()
    assert configs

    for cfg in configs:
        template_id = cfg.get("template_id")
        assert template_id in TEMPLATE_DATA_MODELS
        assert cfg.get("sheet_pattern")
        assert cfg.get("headers", {}).get("data_start_row")

        model = TEMPLATE_DATA_MODELS[template_id]
        model_fields = model._meta.fields_map
        for col in cfg.get("columns", []):
            db_field = col.get("db_field")
            assert db_field in model_fields, (
                f"{template_id}.{db_field} missing from {model._meta.db_table}"
            )

            match = DECIMAL_RE.match(col.get("type", ""))
            if match:
                field = model_fields[db_field]
                assert isinstance(field, fields.DecimalField)
                assert field.max_digits == int(match.group(1))
                assert field.decimal_places == int(match.group(2))
