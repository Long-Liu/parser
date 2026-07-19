"""Deterministic multi-project comparison report (AI fallback).

Five chapters aligned with the multi-project comparison UI report tab:
核心经营总览 / 全项目进度对标 / 成本专项经营分析 / 盈利专项分析 / 项目综合评级.
Pure domain rules over compare_projects metrics: no ORM, no I/O.
"""

from __future__ import annotations


def _fmt(value, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.2f}{suffix}"


def _rank(projects: list[dict], key: str, reverse: bool = True) -> list[dict]:
    """Sort by metric; None values always rank last."""
    return sorted(
        projects,
        key=lambda p: (p[key] is None, -(p[key] or 0) if reverse else (p[key] or 0)),
    )


def build_compare_report(projects: list[dict], ym: str | None) -> list[dict]:
    """Build the five-chapter report from compare_projects ``projects`` metrics."""
    period = ym or "最新月份"
    total_contract = sum(p["contract"] for p in projects)
    total_settlement = sum(p["settlement"] for p in projects)
    total_profit = sum(p["profit"] for p in projects)
    by_score = _rank(projects, "total_score")
    best, worst = by_score[0], by_score[-1]

    overview = (
        f"本报告覆盖 {len(projects)} 个项目（{period}）。"
        f"合同总额 {_fmt(total_contract)}，累计结算 {_fmt(total_settlement)}，"
        f"毛利合计 {_fmt(total_profit)}。"
        f"综合表现最优为「{best['project_name']}」（{best['total_score']:.2f} 分，{best['grade']} 级），"
        f"最弱为「{worst['project_name']}」（{worst['total_score']:.2f} 分，{worst['grade']} 级）。"
    )

    by_progress = _rank(projects, "progress")
    progress_lines = "；".join(
        f"{p['project_name']} {_fmt(p['progress'], '%')}" for p in by_progress
    )
    progress = (
        f"按形象进度排序：{progress_lines}。"
        f"进度领先项目「{by_progress[0]['project_name']}」"
        f"（{_fmt(by_progress[0]['progress'], '%')}），"
        f"落后项目「{by_progress[-1]['project_name']}」"
        f"（{_fmt(by_progress[-1]['progress'], '%')}），"
        "建议对进度落后项目加强工期督导与资源投入。"
    )

    by_unit_cost = _rank(projects, "unit_cost", reverse=False)
    cost_lines = "；".join(
        f"{p['project_name']} 单位成本 {_fmt(p['unit_cost'], '%')}" for p in by_unit_cost
    )
    cost = (
        f"成本管控对标：{cost_lines}。"
        f"「{by_unit_cost[0]['project_name']}」成本管控最优，"
        f"「{by_unit_cost[-1]['project_name']}」单位成本偏高，"
        "建议复核其分包策划调整与现执行预算偏差。"
    )

    by_profit_rate = _rank(projects, "profit_rate")
    profit_lines = "；".join(
        f"{p['project_name']} 毛利率 {_fmt(p['profit_rate'], '%')}" for p in by_profit_rate
    )
    profit = (
        f"盈利能力对标：{profit_lines}。"
        f"「{by_profit_rate[0]['project_name']}」盈利水平领先，"
        f"「{by_profit_rate[-1]['project_name']}」毛利率偏低，"
        "需关注结算产值确认与成本归集的及时性。"
    )

    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    rating_lines = "；".join(
        f"{p['project_name']} {p['total_score']:.2f} 分（{p['grade']} 级）"
        for p in sorted(projects, key=lambda p: (grade_order.get(p["grade"], 4), -p["total_score"]))
    )
    rating = (
        f"项目综合评级：{rating_lines}。"
        "评级由盈利能力、成本管控、进度执行、结算质量、营收转化五维评分加权得出，"
        "建议对 C/D 级项目启动专项经营分析。"
    )

    return [
        {"key": "overview", "title": "核心经营总览", "content": overview},
        {"key": "progress", "title": "全项目进度对标", "content": progress},
        {"key": "cost", "title": "成本专项经营分析", "content": cost},
        {"key": "profit", "title": "盈利专项分析", "content": profit},
        {"key": "rating", "title": "项目综合评级", "content": rating},
    ]
