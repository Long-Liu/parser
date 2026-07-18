"""Tests for the unified YAML template loading pipeline.

YamlTemplateLoader / YamlTemplateCatalog are the only way template configs are
read; these tests keep the original config-loader validation intent: the
template directory can be listed, ids are validated, path traversal is
blocked, and every shipped template still matches its data table.
"""

import os
import re
import tempfile

import pytest
from tortoise import fields

from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
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


def test_template_ids_lists_directory(config_dir):
    loader = YamlTemplateLoader(config_dir=config_dir)
    assert loader.template_ids() == ["test_tpl"]


def test_load_builds_template(config_dir):
    template = YamlTemplateLoader(config_dir=config_dir).load("test_tpl")
    assert str(template.id) == "test_tpl"
    assert template.header_spec.data_start_row == 5
    assert len(template.fixed_columns) == 1


def test_load_all_loads_every_config(config_dir):
    templates = YamlTemplateLoader(config_dir=config_dir).load_all()
    assert len(templates) == 1
    assert str(templates[0].id) == "test_tpl"


def test_load_rejects_invalid_template_id(config_dir):
    loader = YamlTemplateLoader(config_dir=config_dir)
    with pytest.raises(ValueError, match="invalid template_id"):
        loader.load("bad id!")


def test_load_blocks_path_traversal(config_dir):
    loader = YamlTemplateLoader(config_dir=config_dir)
    with pytest.raises(ValueError, match="invalid template_id"):
        loader.load("../secret")


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
    loader = YamlTemplateLoader()
    templates = loader.load_all()
    assert templates
    assert loader.template_ids()

    for template in templates:
        template_id = str(template.id)
        assert template_id in TEMPLATE_DATA_MODELS
        assert template.sheet_pattern
        assert template.header_spec.data_start_row

        model = TEMPLATE_DATA_MODELS[template_id]
        model_fields = model._meta.fields_map
        for col in template.fixed_columns:
            db_field = col.db_field
            assert db_field in model_fields, (
                f"{template_id}.{db_field} missing from {model._meta.db_table}"
            )

            match = DECIMAL_RE.match(col.db_type or "")
            if match:
                field = model_fields[db_field]
                assert isinstance(field, fields.DecimalField)
                assert field.max_digits == int(match.group(1))
                assert field.decimal_places == int(match.group(2))
