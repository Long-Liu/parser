"""hierarchy_code 解析与 DataRowExtractor 层级编码填充测试。"""

from datetime import datetime

import pytest

from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.hierarchy_code import parse_hierarchy_code
from contexts.template.domain.template import (
    ColumnMapping,
    HeaderSpec,
    HierarchyConfig,
    Template,
    TemplateId,
)
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader


# ── parse_hierarchy_code：合法序号 ──────────────────────────────────

@pytest.mark.parametrize("value,separator,expected", [
    ("一", ".", "一"),
    ("十一", ".", "十一"),
    ("一、", ".", "一"),          # 顿号后缀剥离
    ("1", ".", "1"),
    ("1.2", ".", "1.2"),
    ("1.2.3", ".", "1.2.3"),
    ("1.", ".", "1"),             # 尾部多余分隔符剥离
    ("２", ".", "2"),             # 全角数字归一
    ("（一）", "-", "(一)"),      # 全角括号归一
    ("1-1", "-", "1-1"),
    ("2-3", "-", "2-3"),
    ("标段一", ".", "标段一"),
    ("1BA", "", "1BA"),           # 空分隔符：编码列任意非空文本
    ("GT1-3", "", "GT1-3"),
    ("1AAAAACA0301", "", "1AAAAACA0301"),
    (2, ".", "2"),                # 数值型单元格
    (2.0, ".", "2"),
    (1.5, ".", "1.5"),
])
def test_parse_valid_hierarchy_codes(value, separator, expected):
    assert parse_hierarchy_code(value, separator) == expected


# ── parse_hierarchy_code：非层级格式 → None ─────────────────────────

@pytest.mark.parametrize("value,separator", [
    (None, "."),
    ("", "."),
    ("   ", "."),
    ("拆分", "."),
    ("总计", "."),
    ("建筑材料费", "."),
    ("注：详见附图", "."),
    (datetime(2026, 3, 1), "."),
    (True, "."),
    ("x" * 60, ""),               # 超过 varchar(50) 上限
])
def test_parse_rejects_non_hierarchy_values(value, separator):
    assert parse_hierarchy_code(value, separator) is None


# ── DataRowExtractor：按模板 hierarchy 配置填充 ─────────────────────

def _make_template(**kwargs) -> Template:
    defaults = dict(
        template_id=TemplateId("t"),
        sheet_pattern="*",
        header_spec=HeaderSpec(header_rows=[1], data_start_row=2),
        hierarchy_config=HierarchyConfig(column_name="序号", separator="."),
        fixed_columns=[
            ColumnMapping(db_field="name", match_headers=["名称"]),
        ],
    )
    defaults.update(kwargs)
    return Template(**defaults)


def test_extract_fills_hierarchy_code():
    template = _make_template()
    grid = [
        ["序号", "名称"],
        ["一", "建筑工程"],
        ["1", "土建"],
        ["1.1", "基础"],
        [None, "无序号行"],
        ["说明文字", "非层级序号行"],
    ]
    rows = DataRowExtractor().extract(grid, ["序号", "名称"], template)
    assert [r.hierarchy_code for r in rows] == ["一", "1", "1.1", None, None]
    assert [r.fields["name"] for r in rows] == [
        "建筑工程", "土建", "基础", "无序号行", "非层级序号行",
    ]


def test_extract_resolves_column_name_with_inner_spaces():
    """concrete_ledger 的 column_name 为 '序  号'（含全角/半角空格）。"""
    template = _make_template(
        hierarchy_config=HierarchyConfig(column_name="序  号", separator=".")
    )
    grid = [
        ["序  号", "名称"],
        ["1", "浇筑记录"],
    ]
    rows = DataRowExtractor().extract(grid, ["序  号", "名称"], template)
    assert rows[0].hierarchy_code == "1"


def test_extract_hierarchy_with_dash_separator():
    template = _make_template(
        hierarchy_config=HierarchyConfig(column_name="序号", separator="-")
    )
    grid = [
        ["序号", "名称"],
        ["一", "全厂机械"],
        ["（一）", "建筑机械"],
        ["1-1", "1#平臂吊"],
    ]
    rows = DataRowExtractor().extract(grid, ["序号", "名称"], template)
    assert [r.hierarchy_code for r in rows] == ["一", "(一)", "1-1"]


def test_extract_without_hierarchy_config_keeps_none():
    template = _make_template(hierarchy_config=None)
    grid = [["序号", "名称"], ["1", "x"]]
    rows = DataRowExtractor().extract(grid, ["序号", "名称"], template)
    assert rows[0].hierarchy_code is None


def test_extract_hierarchy_column_missing_from_sheet():
    """表内找不到序号列时不中断，hierarchy_code 全为 None。"""
    template = _make_template()
    grid = [["别的", "名称"], ["1", "x"]]
    rows = DataRowExtractor().extract(grid, ["别的", "名称"], template)
    assert len(rows) == 1
    assert rows[0].hierarchy_code is None


# ── 真实 material_cost.yaml 端到端 ──────────────────────────────────

def test_material_cost_real_template_fills_hierarchy():
    template = YamlTemplateLoader().load("material_cost")
    flat_headers = [
        "序号", "预算科目", "单位",
        "经济考核指标_数量", "经济考核指标_单价", "经济考核指标_合价",
    ]
    grid = [
        ["序号", "预算科目", "单位", "经济考核指标（初版预算）", None, None],
        [None, None, None, "数量", "单价", "合价"],
        ["一", "建筑材料费", None, None, None, 70388700],
        ["1", "混凝土", "m³", 88829.39, 330, 29313700],
        ["2", "钢筋", "t", 11532.28, 3240, 37364600],
        ["二", "安装材料费", None, None, None, 33360425.7],
        ["1.1", "钢管类(新)-不锈钢", "t", 55.176, 25416.67, 1402390],
    ]
    rows = DataRowExtractor().extract(grid, flat_headers, template)
    assert [r.hierarchy_code for r in rows] == ["一", "1", "2", "二", "1.1"]
    assert rows[1].fields["budget_category"] == "混凝土"
