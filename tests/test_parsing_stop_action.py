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
    total_rules = [r for r in template.stop_rules if any("总" in pattern for pattern in r.patterns)]
    assert len(total_rules) == 1
    assert total_rules[0].action == StopRuleAction.LAST
    assert total_rules[0].columns == []
    assert total_rules[0].label_field == "budget_category"


def test_all_action_last_templates_load():
    """新电源A模板的终结合计行规则必须标记 action:"last"。

    These templates retain their actual workbook subtotal/total row.
    """
    loader = YamlTemplateLoader()
    expected = {
        "material_cost": "budget_category",
        "installation_dynamic": "project_name",
        "other_items": "item_name",
        "machinery": "machine_name",
        "construction_dynamic": "project_name",
        "budget_adjustment_summary": "item_name",
        "budget_adjustment_internal": "project_name",
        "budget_increase": "increase_count",
        "budget_lease": "request_name",
    }
    for template_id, label_field in expected.items():
        template = loader.load(template_id)
        total_rules = [rule for rule in template.stop_rules if rule.patterns]
        assert len(total_rules) == 1, template_id
        assert total_rules[0].action == StopRuleAction.LAST, template_id
        assert total_rules[0].columns == [], template_id
        assert total_rules[0].label_field == label_field, template_id


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


def test_exact_total_pattern_does_not_match_note_text():
    rule = StopRule(
        rule_type=StopRuleType.CELL_MATCH,
        patterns=[r"^\s*合\s*计\s*$"],
    )
    detector = StopDetector()
    assert detector.should_stop(0, [[None, "合 计"]], [rule]) is True
    assert detector.should_stop(0, [[None, "备注：合计金额待确认"]], [rule]) is False


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
    template = _make_template(
        stop_rules=[
            StopRule(rule_type=StopRuleType.CELL_MATCH, patterns=[r"^总计"]),
        ]
    )
    rows = DataRowExtractor().extract(_grid_with_total(), ["名称", "金额"], template)
    assert [r.fields["name"] for r in rows] == ["混凝土", "钢筋"]


def test_action_last_includes_matched_row_as_final_row():
    template = _make_template(
        stop_rules=[
            StopRule(
                rule_type=StopRuleType.CELL_MATCH,
                patterns=[r"^总计"],
                action=StopRuleAction.LAST,
            ),
        ]
    )
    rows = DataRowExtractor().extract(_grid_with_total(), ["名称", "金额"], template)
    assert [r.fields.get("name") for r in rows] == ["混凝土", "钢筋", None]
    assert rows[-1].fields["amount"] == "总计"
    assert rows[-1].row_index == 4


def test_action_last_moves_numeric_column_marker_to_configured_label_field():
    template = _make_template(
        fixed_columns=[
            ColumnMapping(db_field="name", match_headers=["名称"], db_type="varchar(100)"),
            ColumnMapping(db_field="amount", match_headers=["金额"], db_type="decimal(15,2)"),
        ],
        stop_rules=[
            StopRule(
                rule_type=StopRuleType.CELL_MATCH,
                patterns=[r"^\s*合\s*计\s*$"],
                action=StopRuleAction.LAST,
                label_field="name",
            ),
        ]
    )
    rows = DataRowExtractor().extract(
        [["名称", "金额"], ["钢筋", 200], [None, "合计"], ["尾注", 999]],
        ["名称", "金额"],
        template,
    )
    assert len(rows) == 2
    assert rows[-1].fields == {"name": "合计", "amount": None}
    assert rows[-1].row_index == 3


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
