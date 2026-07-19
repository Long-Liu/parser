"""Five-dimension project comparison scoring model.

Thresholds mirror the multi-project comparison UI (盈利能力/成本管控/进度执行/
结算质量/营收转化 + A-D grade). Pure domain rules: no ORM, no I/O.

Convention: a metric that cannot be computed (division by zero) is passed as
None and the dimension falls back to its lowest band.
"""

from __future__ import annotations


def _profitability(profit_rate: float | None) -> int:
    """盈利能力: based on profit_rate (%)."""
    if profit_rate is None:
        return 40
    if profit_rate >= 18:
        return 90
    if profit_rate >= 15:
        return 75
    if profit_rate >= 10:
        return 60
    return 40


def _cost_control(unit_cost: float | None) -> int:
    """成本管控: based on unit_cost = total_cost / revenue * 100 (lower is better)."""
    if unit_cost is None:
        return 40
    if unit_cost <= 82:
        return 90
    if unit_cost <= 86:
        return 75
    if unit_cost <= 90:
        return 60
    return 40


def _progress_execution(progress: float | None) -> int:
    """进度执行: based on project progress (%)."""
    if progress is None:
        return 50
    if progress >= 88:
        return 85
    if progress >= 80:
        return 75
    if progress >= 70:
        return 65
    return 50


def _settlement_quality(settlement_rate: float | None) -> int:
    """结算质量: based on settlement_rate = settlement / contract * 100."""
    if settlement_rate is None:
        return 45
    if settlement_rate >= 85:
        return 88
    if settlement_rate >= 78:
        return 74
    if settlement_rate >= 70:
        return 62
    return 45


def _revenue_conversion(revenue_ratio: float | None) -> int:
    """营收转化: based on revenue_ratio = revenue / settlement * 100."""
    if revenue_ratio is None:
        return 45
    if revenue_ratio >= 94:
        return 88
    if revenue_ratio >= 90:
        return 74
    if revenue_ratio >= 85:
        return 62
    return 45


def grade_for(total_score: float) -> str:
    if total_score >= 83:
        return "A"
    if total_score >= 70:
        return "B"
    if total_score >= 58:
        return "C"
    return "D"


def compare_scores(
    *,
    profit_rate: float | None,
    unit_cost: float | None,
    progress: float | None,
    settlement_rate: float | None,
    revenue_ratio: float | None,
) -> dict:
    """Score one project's comparison metrics on five dimensions.

    Returns {"scores": {dimension: int}, "total_score": float, "grade": str};
    total_score is the mean of the five dimension scores.
    """
    scores = {
        "profitability": _profitability(profit_rate),
        "cost_control": _cost_control(unit_cost),
        "progress_execution": _progress_execution(progress),
        "settlement_quality": _settlement_quality(settlement_rate),
        "revenue_conversion": _revenue_conversion(revenue_ratio),
    }
    total = round(sum(scores.values()) / len(scores), 2)
    return {"scores": scores, "total_score": total, "grade": grade_for(total)}
