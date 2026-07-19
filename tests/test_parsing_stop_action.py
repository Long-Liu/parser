"""stop rule action 语义测试：默认剔除匹配行，action:"last" 纳入后停止。"""

from contexts.parsing.domain.data_extractor import DataRowExtractor
from contexts.parsing.domain.stop_detector import StopDetector
from contexts.template.domain.template import (
    ColumnMapping,
    HeaderSpec,
    StopRule,
    StopRuleAction,
    StopRuleType,
    Template,
    TemplateId,
)
from contexts.template.infrastructure.yaml_loader import YamlTemplateLoader


def _make_template(**kwargs) -> Template:
    defaults = dict(
        template_id=TemplateId("t"),
        sheet_pattern="*",
        header_spec=HeaderSpec(header_rows=[1], data_start_row=2),
        fixed_columns=[
            ColumnMapping(db_field="name", match_headers=["名称"]),
            ColumnMapping(db_field="amount", match_headers=["金额"]),
        ],
        stop_rules=[],
    )
    defaults.update(kwargs)
    return Template(**defaults)


# ── yaml_loader 读取 action ──────────────────────────────────────────

def test_yaml_loader_reads_action_last():
    template = YamlTemplateLoader().load("material_cost")
    total_rules = [r for r in template.stop_rules if "^总计" in r.patterns]
    assert len(total_rules) == 1
    assert total_rules[0].action == StopRuleAction.LAST


def test_yaml_loader_default_action_is_exclude():
    template = YamlTemplateLoader().load("material_cost")
    note_rules = [r for r in template.stop_rules if "^注：" in r.patterns]
    assert len(note_rules) == 1
    assert note_rules[0].action == StopRuleAction.EXCLUDE


def test_all_action_last_templates_load():
    """新电源A模板的终结合计行规则必须标记 action:"last"。

    远端模板重构后 rebar_ledger 等旧表已删除；construction_dynamic 另有一条
    默认 exclude 的 "^合计"（I 列）规则，与 "合计（含税）" 终结行规则并存，
    因此按精确 pattern 断言而非集合相等。
    """
    loader = YamlTemplateLoader()
    expected = {
        "material_cost": "^总计",
        "construction_dynamic": "^合计（含税）",
        "installation_dynamic": "^合计",
        "other_items": "^合计",
        "machinery": "^小计",
        "social_insurance": "^合计",
    }
    for template_id, pattern in expected.items():
        template = loader.load(template_id)
        actions = {
            r.action for r in template.stop_rules
            if pattern in r.patterns
        }
        assert actions == {StopRuleAction.LAST}, template_id


# ── StopDetector：match_rule 与空 columns 扫描全行 ──────────────────

def test_match_rule_returns_fired_rule():
    rule = StopRule(
        rule_type=StopRuleType.CELL_MATCH,
        patterns=[r"^总计"],
        action=StopRuleAction.LAST,
    )
    grid = [["数据"], [None, "总计"]]
    fired = StopDetector().match_rule(1, grid, [rule])
    assert fired is rule
    assert StopDetector().match_rule(0, grid, [rule]) is None


def test_cell_match_without_columns_scans_all_cells():
    """未配置 columns 的规则扫描整行（'总计' 常合并/落在非 A 列）。"""
    rule = StopRule(
        rule_type=StopRuleType.CELL_MATCH,
        patterns=[r"^总计"],
    )
    grid = [["a", "b", "c"], ["x", "y", "总计"]]
    detector = StopDetector()
    assert detector.should_stop(0, grid, [rule]) is False
    assert detector.should_stop(1, grid, [rule]) is True


# ── DataRowExtractor：action 语义 ────────────────────────────────────

def _grid_with_total():
    return [
        ["名称", "金额"],
        ["混凝土", 100],
        ["钢筋", 200],
        [None, "总计"],
        ["不应被解析", 999],
    ]


def test_default_action_excludes_matched_row():
    template = _make_template(stop_rules=[
        StopRule(rule_type=StopRuleType.CELL_MATCH, patterns=[r"^总计"]),
    ])
    rows = DataRowExtractor().extract(
        _grid_with_total(), ["名称", "金额"], template
    )
    assert [r.fields["name"] for r in rows] == ["混凝土", "钢筋"]


def test_action_last_includes_matched_row_as_final_row():
    template = _make_template(stop_rules=[
        StopRule(
            rule_type=StopRuleType.CELL_MATCH,
            patterns=[r"^总计"],
            action=StopRuleAction.LAST,
        ),
    ])
    rows = DataRowExtractor().extract(
        _grid_with_total(), ["名称", "金额"], template
    )
    assert [r.fields.get("name") for r in rows] == ["混凝土", "钢筋", None]
    assert rows[-1].fields["amount"] == "总计"
    assert rows[-1].row_index == 4


def test_material_cost_real_yaml_total_row_ingested():
    """material_cost.yaml 端到端：总计行入库、其后注行不解析。"""
    template = YamlTemplateLoader().load("material_cost")
    flat_headers = ["序号", "成本科目", "单位", "经济考核指标_合价"]
    grid = [
        ["序号", "成本科目", "单位", "经济考核指标（初版预算）"],
        [None, None, None, "合价"],
        ["一", "建筑材料费", None, 70388700],
        ["1", "混凝土", "m³", 29313700],
        [None, "总计", None, 107749125.7],
        ["注：本表含税金", None, None, None],
    ]
    rows = DataRowExtractor().extract(grid, flat_headers, template)
    assert len(rows) == 3
    assert rows[-1].fields["budget_category"] == "总计"
    assert rows[-1].fields["indicator_total"] == 107749125.7
    assert rows[-1].hierarchy_code is None
