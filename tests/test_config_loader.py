import pytest
import tempfile
import os
from utils.config_loader import load_config, list_configs, match_template


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
