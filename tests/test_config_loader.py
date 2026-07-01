import pytest
import tempfile
import os
import re
import sqlalchemy as sa

from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_TABLES
from contexts.template.infrastructure.config_loader import (
    load_config,
    list_configs,
    match_template,
)


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


def test_match_template(config_dir):
    config = match_template("表1 人工费-动态", config_dir=config_dir)
    assert config is not None
    assert config["template_id"] == "test_tpl"


def test_match_template_no_match(config_dir):
    config = match_template("不存在的Sheet名", config_dir=config_dir)
    assert config is None


def test_all_template_configs_match_data_tables():
    configs = list_configs()
    assert configs

    for cfg in configs:
        template_id = cfg.get("template_id")
        assert template_id in TEMPLATE_DATA_TABLES
        assert cfg.get("sheet_pattern")
        assert cfg.get("headers", {}).get("data_start_row")

        table = TEMPLATE_DATA_TABLES[template_id]
        table_cols = set(table.c.keys())
        for col in cfg.get("columns", []):
            db_field = col.get("db_field")
            assert db_field in table_cols, f"{template_id}.{db_field} missing from {table.name}"

            match = DECIMAL_RE.match(col.get("type", ""))
            if match:
                table_type = table.c[db_field].type
                assert isinstance(table_type, sa.Numeric)
                assert table_type.precision == int(match.group(1))
                assert table_type.scale == int(match.group(2))
