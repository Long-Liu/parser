from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

# noinspection PyPackageRequirements
from tortoise.expressions import Q, Subquery

# noinspection PyPackageRequirements
from tortoise.functions import Count, Sum

from contexts.alert.infrastructure.tables import AlertModel
from contexts.analytics.domain.compare_report import build_compare_report
from contexts.analytics.domain.hierarchy import resolve_hierarchy_paths
from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.analytics.domain.repositories import AnalyticsRepository
from contexts.analytics.domain.scoring import compare_scores
from contexts.auth.infrastructure.tables import Notification, NotificationRead, User
from contexts.parsing.infrastructure.data_cleanup import ParsedDataCleanup
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.tables import Project, ProjectMilestone
from contexts.shared.application.transaction import (
    NoopTransactionManager,
    TransactionManager,
)
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.database.tables import (
    SETTLE_CONTRACT_PRICE,
    SETTLE_CUMULATIVE_COST,
    SETTLE_CUMULATIVE_OUTPUT,
    SETTLE_CURRENT_PROFIT,
    SETTLE_CURRENT_PROFIT_RATE,
    SETTLE_FORECAST_COST,
    SETTLE_FORECAST_PROFIT,
    SETTLE_FORECAST_PROFIT_RATE,
    SETTLE_FORECAST_REVENUE,
    DataBudgetLease,
    DataConstructionDynamic,
    DataDynamicIndicator,
    DataInstallationDynamic,
    DataMaterialCost,
    DataSettlementOutput,
    settlement_indicator_map,
)

logger = logging.getLogger("parser.analytics")


def _number(value) -> float:
    return float(value) if value is not None else 0.0


def _number_or_none(value) -> float | None:
    """Convert a numeric cell to float, preserving None for absent values.

    Unlike ``_number`` (missing -> 0.0), callers that format or threshold
    rates keep None so missing data is not presented as a 0% figure.
    """
    return float(value) if value is not None else None


def _rate(profit: float, revenue: float) -> float:
    return round(profit / revenue * 100, 2) if revenue else 0.0


def _settle(indicators: dict, *names: str) -> float:
    """First non-None cumulative_value among the given settlement indicators."""
    for name in names:
        value = indicators.get(name)
        if value is not None:
            return float(_number(value))
    return 0.0


def _settle_rate(indicators: dict, name: str, profit: float, revenue: float) -> float:
    """Settlement rate indicators are stored as ratios (0.x); the API reports
    percents, so convert. Fall back to profit/revenue when the row is absent."""
    value = indicators.get(name)
    if value is not None:
        return round(_number(value) * 100, 2)
    return _rate(profit, revenue)


def _sum_lease_rows(rows: list, field: str) -> float:
    return round(sum(_number(getattr(row, field)) for row in rows), 2)


class TortoiseAnalyticsRepository(AnalyticsRepository):
    _REPORT_CATALOG: list[dict] = [
        {"type": "report", "id": "cost-categories", "title": "成本科目", "subtitle": "多项目成本对比"},
        {"type": "report", "id": "project-profits", "title": "项目毛利情况", "subtitle": "项目盈利分析"},
        {"type": "report", "id": "dashboard", "title": "数据大屏", "subtitle": "经营监控中心"},
    ]

    def __init__(
        self,
        ai_provider: AIAnalysisPort | None = None,
        data_cleanup: ParsedDataCleanup | None = None,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        self._ai_provider = ai_provider
        self._data_cleanup = data_cleanup or ParsedDataCleanup()
        self._tx = transaction_manager or NoopTransactionManager()

    async def project_summary(self, project_ids: list[int] | None = None) -> dict:
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        aggregates = await query.annotate(
            total=Count("id"),
            normal=Count("id", _filter=Q(status="normal")),
            warning=Count("id", _filter=Q(status="warning")),
            contract_total=Sum("contract_price"),
        ).values("total", "normal", "warning", "contract_total")
        row = aggregates[0] if aggregates else {}
        return {
            "total": int(row.get("total") or 0),
            "normal": int(row.get("normal") or 0),
            "warning": int(row.get("warning") or 0),
            "contract_total": float(row.get("contract_total") or Decimal("0")),
        }

    async def monthly_data(self, project_id: int, pagination: Pagination) -> dict:
        await self._project(project_id)
        months = list(
            await UploadBatch.filter(
                project_id=project_id,
                status="success",
            )
            .order_by("-ym")
            .distinct()
            .values_list("ym", flat=True)
        )
        total = len(months)
        selected = months[pagination.offset : pagination.offset + pagination.size]
        batches_by_month: dict[str, UploadBatch] = {}
        if selected:
            for batch in await UploadBatch.filter(
                project_id=project_id,
                status="success",
                ym__in=selected,
            ).order_by("ym", "-id"):
                if batch.ym not in batches_by_month:
                    batches_by_month[batch.ym] = batch
        batches = [batches_by_month[month] for month in selected if month in batches_by_month]
        data_by_batch = await self._monthly_data_maps([batch.id for batch in batches])
        items = [
            self._monthly_item_from_data(
                batch,
                data_by_batch["settlement"].get(batch.id, []),
                data_by_batch["dynamic"].get(batch.id, []),
                data_by_batch["lease"].get(batch.id, []),
            )
            for batch in batches
        ]
        return {"data": items, "pagination": {"page": pagination.page, "size": pagination.size, "total": total}}

    async def month_comparison(self, project_id: int, months: list[str]) -> dict:
        await self._project(project_id)
        if len(set(months)) < 2:
            raise ValidationError("at least two months are required")
        batches = await UploadBatch.filter(
            project_id=project_id,
            ym__in=list(set(months)),
            status="success",
        ).order_by("ym", "-id")
        # 批量加载全部月份的数据，避免逐月 4 次查询（settlement/dynamic/lease + 成本科目）。
        batch_ids = [batch.id for batch in batches]
        data_maps = await self._monthly_data_maps(batch_ids)
        cost_rows = (
            await DataDynamicIndicator.filter(batch_id__in=batch_ids).exclude(item_name=None).order_by("id")
            if batch_ids
            else []
        )
        costs_by_batch: dict[int, list[DataDynamicIndicator]] = defaultdict(list)
        for row in cost_rows:
            costs_by_batch[row.batch_id].append(row)
        seen = set()
        items = []
        for batch in batches:
            if batch.ym in seen:
                continue
            seen.add(batch.ym)
            item = self._monthly_item_from_data(
                batch,
                data_maps["settlement"].get(batch.id, []),
                data_maps["dynamic"].get(batch.id, []),
                data_maps["lease"].get(batch.id, []),
            )
            costs = [
                {
                    "hierarchy_code": row.hierarchy_code,
                    "name": row.item_name,
                    "actual": _number(row.incurred_cost),
                    "forecast": _number(
                        row.forecast_with_tax if row.forecast_with_tax is not None else row.estimated_with_tax
                    ),
                }
                for row in costs_by_batch.get(batch.id, [])
            ]
            resolve_hierarchy_paths(costs)
            item["cost_categories"] = costs
            items.append(item)
        # 环比：每个月份相对前一个选中月份（items 按 ym 升序）的指标变化；
        # 首个选中月份无基期，mom 为 None。
        for index, item in enumerate(items):
            item["mom"] = None if index == 0 else self._mom_change(items[index - 1], item)
        return {"project_id": project_id, "months": items}

    @staticmethod
    def _mom_change(previous: dict, current: dict) -> dict:
        """Month-over-month change for each metric.

        change: absolute difference (profit_rate 以百分点 pp 表示，因其本身为百分数);
        change_pct: (current - previous) / previous * 100, None when base is 0.
        """
        mom = {}
        for metric in ("revenue", "cost", "profit", "profit_rate"):
            change = round(current[metric] - previous[metric], 2)
            base = previous[metric]
            mom[metric] = {
                "change": change,
                "change_pct": round(change / base * 100, 2) if base else None,
            }
        return mom

    async def compare_projects(self, project_ids: list[int] | None, ym: str | None) -> dict:
        project_ids = list(project_ids or [])
        if len(set(project_ids)) < 2:
            raise ValidationError("at least two projects are required")
        projects = await Project.filter(id__in=project_ids).order_by("id")
        costs, batch_map = await asyncio.gather(
            self.cost_categories(project_ids, ym, Pagination(1, 100, max_size=100)),
            self._latest_batch_map([project.id for project in projects], ym),
        )
        batch_ids = [batch.id for batch in batch_map.values()]
        indicator_maps: dict[int, dict] = {}
        if batch_ids:
            settlement_rows = await DataSettlementOutput.filter(batch_id__in=batch_ids)
            rows_by_batch: dict[int, list[DataSettlementOutput]] = {}
            for row in settlement_rows:
                rows_by_batch.setdefault(row.batch_id, []).append(row)
            indicator_maps = {
                batch_id: settlement_indicator_map(rows)
                for batch_id, rows in rows_by_batch.items()
            }
        metrics = [
            self._compare_item_from_data(
                project,
                batch_map.get(project.id),
                indicator_maps.get(batch_map[project.id].id, {}) if project.id in batch_map else {},
                ym,
            )
            for project in projects
        ]
        profits = [
            {
                "project_id": item["project_id"],
                "project_name": item["project_name"],
                "ym": item["ym"],
                "profit": item["profit"],
                "profit_rate": item["profit_rate"],
            }
            for item in metrics
        ]
        # cost_categories/profits kept for backward compatibility; "projects"
        # carries the 9-metric comparison table plus five-dimension scores.
        return {"cost_categories": costs["projects"], "profits": profits, "projects": metrics}

    @staticmethod
    def _compare_item_from_data(
        project: Project,
        batch: UploadBatch | None,
        indicators: dict,
        ym: str | None,
    ) -> dict:
        contract = _number(project.contract_price)
        # 累计结算（截至当前实际·累计已结算）：取结算表产值行，缺行时回退表内
        # 合同总价行（与 _profit_item current 口径一致）；整批无数据时保持全零，
        # 不回退项目合同价，以免无数据项目虚增评分。
        settlement = _settle(indicators, SETTLE_CUMULATIVE_OUTPUT, SETTLE_CONTRACT_PRICE)
        profit = _settle(indicators, SETTLE_CURRENT_PROFIT)
        total_cost = _settle(indicators, SETTLE_CUMULATIVE_COST) if indicators else settlement - profit
        # 现有数据模型无独立"营收"列，营收与累计结算同源（revenue_ratio 恒为 100 或 None，
        # 待模板扩展独立营收列后区分）。
        revenue = settlement
        # 毛利率优先取结算表存储口径（比率 → 百分比）；除零一律 None，
        # 对应评分维度按最低档计（见 domain/scoring.py）。
        stored_rate = indicators.get(SETTLE_CURRENT_PROFIT_RATE)
        profit_rate: float | None
        if stored_rate is not None:
            profit_rate = round(_number(stored_rate) * 100, 2)
        else:
            profit_rate = round(profit / revenue * 100, 2) if revenue else None
        settlement_rate = round(settlement / contract * 100, 2) if contract else None
        revenue_ratio = round(revenue / settlement * 100, 2) if settlement else None
        unit_cost = round(total_cost / revenue * 100, 2) if revenue else None
        scored = compare_scores(
            profit_rate=profit_rate,
            unit_cost=unit_cost,
            progress=_number(project.progress),
            settlement_rate=settlement_rate,
            revenue_ratio=revenue_ratio,
        )
        return {
            "project_id": project.id,
            "project_code": project.code,
            "project_name": project.name,
            "ym": batch.ym if batch else ym,
            "progress": _number(project.progress),
            "contract": contract,
            "settlement": settlement,
            "revenue": revenue,
            "total_cost": total_cost,
            "profit": profit,
            "profit_rate": profit_rate,
            "settlement_rate": settlement_rate,
            "revenue_ratio": revenue_ratio,
            "unit_cost": unit_cost,
            **scored,
        }

    async def delete_monthly_data(self, project_id: int, ym: str) -> None:
        async with self._tx.transaction():
            await self._project(project_id)
            batches = await UploadBatch.filter(project_id=project_id, ym=ym)
            batch_ids = [batch.id for batch in batches]
            if not batch_ids:
                raise NotFoundError(f"monthly data {ym} not found")
            await self._data_cleanup.delete_for_batches(batch_ids)

    async def cost_categories(self, project_ids: list[int] | None, ym: str | None, pagination: Pagination) -> dict:
        projects = (
            await Project.filter(id__in=project_ids).order_by("id")
            if project_ids
            else await Project.all().order_by("id")
        )
        batch_map = await self._latest_batch_map([project.id for project in projects], ym)
        batch_ids = [batch.id for batch in batch_map.values()]
        rows_by_batch: dict[int, list[DataDynamicIndicator]] = {batch_id: [] for batch_id in batch_ids}
        if batch_ids:
            rows = await DataDynamicIndicator.filter(
                batch_id__in=batch_ids,
            ).exclude(item_name=None).order_by("batch_id", "id")
            for row in rows:
                rows_by_batch[row.batch_id].append(row)
        series = []
        totals = []
        for project in projects:
            batch = batch_map.get(project.id)
            rows = rows_by_batch.get(batch.id, []) if batch else []
            total = len(rows)
            totals.append(total)
            # 层级路径解析是位置状态机（中文数字大类下编号会重启），必须在
            # 完整有序行集上运行后再分页切片，不能先 OFFSET/LIMIT。
            items = []
            for row in rows:
                indicator = _number(row.indicator_with_tax)
                actual = _number(row.incurred_cost)
                deviation = round(actual - indicator, 2)
                items.append(
                    {
                        "hierarchy_code": row.hierarchy_code,
                        "name": row.item_name,
                        "indicator": indicator,
                        "actual": actual,
                        "deviation": deviation,
                        # 偏差率沿用旧行为：用未取整差值计算（round 后偏差与旧版
                        # 可能在半分位边界差 0.01pp，这里保持与历史值一致）。
                        "deviation_rate": _rate(actual - indicator, indicator),
                        # 六口径补充列（data_dynamic_indicator 现有列）：
                        "list_target": _number(row.estimated_with_tax),  # 预计完工量含税指标
                        "adj_target": _number(row.adjusted_with_tax),  # 分包策划调整后指标
                        "budget": _number(row.current_budget),  # 现执行预算
                        # 新数据优先使用预计完工成本（动态情况）含税值；
                        # 迁移前存量数据回退预计完工量含税指标。
                        "forecast": _number(
                            row.forecast_with_tax if row.forecast_with_tax is not None else row.estimated_with_tax
                        ),
                    }
                )
            # hierarchy_code 重写为全路径（如 "二.2.1"）并补 level；
            # 存量数据该列为 NULL 的行保持平铺（level=None）。
            resolve_hierarchy_paths(items)
            series.append(
                {
                    "project": {"id": project.id, "code": project.code, "name": project.name},
                    "ym": batch.ym if batch else ym,
                    "items": items[pagination.offset : pagination.offset + pagination.size],
                }
            )
        return {
            "projects": series,
            "pagination": {"page": pagination.page, "size": pagination.size, "total": max(totals, default=0)},
        }

    async def cost_details(self, project_id: int, ym: str | None, pagination: Pagination) -> dict:
        result = await self.cost_categories([project_id], ym, pagination)
        if not result["projects"]:
            raise NotFoundError(f"project {project_id} not found")
        project = result["projects"][0]
        rows = project["items"]
        return {"project": project["project"], "ym": project["ym"], "data": rows, "pagination": result["pagination"]}

    async def project_analysis(self, project_id: int, ym: str | None) -> dict:
        project = await self._project(project_id)
        profit = await self._profit_for(project_id, ym)
        cost = await self.cost_details(project_id, ym, Pagination(1, 100, max_size=100))
        return {
            "project": {
                "id": project.id,
                "code": project.code,
                "name": project.name,
                "status": project.status,
                "progress": _number(project.progress),
                "contract_price": _number(project.contract_price),
            },
            "ym": cost["ym"],
            "profit": profit,
            "cost_categories": cost["data"],
            "milestones": (await self.milestones(project_id, Pagination(1, 100, max_size=100)))["milestones"],
        }

    async def milestones(self, project_id: int, pagination: Pagination) -> dict:
        await self._project(project_id)
        query = ProjectMilestone.filter(project_id=project_id)
        total = await query.count()
        rows = await query.order_by("-ym", "-id").offset(pagination.offset).limit(pagination.size)
        return {
            "milestones": [self._milestone(row) for row in rows],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def project_progress(self, project_id: int, pagination: Pagination) -> dict:
        result = await self.milestones(project_id, pagination)
        return {
            "progress": [
                {
                    "id": row["id"],
                    "ym": row["ym"],
                    "progress": row["progress"],
                    "completion": row["description"],
                    "latest_milestone": row["title"],
                    "completed_at": row["completed_at"],
                }
                for row in result["milestones"]
            ],
            "pagination": result["pagination"],
        }

    async def create_milestone(self, project_id: int, data: dict) -> dict:
        async with self._tx.transaction():
            await self._project(project_id)
            if not data.get("ym") or not data.get("title"):
                raise ValidationError("ym and title are required")
            row = await ProjectMilestone.create(
                project_id=project_id,
                ym=data["ym"],
                title=data["title"].strip(),
                progress=Decimal(str(data.get("progress", 0))),
                description=data.get("description", ""),
                completed_at=data.get("completed_at") or None,
            )
            return self._milestone(row)

    async def update_milestone(self, project_id: int, milestone_id: int, data: dict) -> dict:
        async with self._tx.transaction():
            row = await ProjectMilestone.get_or_none(
                id=milestone_id,
                project_id=project_id,
            )
            if row is None:
                raise NotFoundError(f"milestone {milestone_id} not found")
            for field in ("ym", "title", "description", "completed_at"):
                if field in data:
                    setattr(row, field, data[field] or None)
            if "progress" in data:
                row.progress = Decimal(str(data["progress"]))
            await row.save()
            return self._milestone(row)

    async def delete_milestone(self, project_id: int, milestone_id: int) -> None:
        async with self._tx.transaction():
            deleted = await ProjectMilestone.filter(
                id=milestone_id,
                project_id=project_id,
            ).delete()
            if not deleted:
                raise NotFoundError(f"milestone {milestone_id} not found")

    async def project_profits(
        self, ym: str | None, pagination: Pagination, project_ids: list[int] | None = None
    ) -> dict:
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        total = await query.count()
        projects = await query.order_by("id").offset(pagination.offset).limit(pagination.size)
        batch_map, profit_map, indicator_map = await self._load_batches(projects, ym)
        items = [self._profit_item(p, batch_map, profit_map, indicator_map, ym) for p in projects]
        return {"projects": items, "pagination": {"page": pagination.page, "size": pagination.size, "total": total}}

    async def budget_lease_writeoffs(
        self,
        ym: str | None,
        pagination: Pagination,
        project_ids: list[int] | None = None,
    ) -> dict:
        """Aggregate 表10.3 by project for the budget lease/write-off UI.

        The published UI renames the source workbook's three lease calibers:
        定标/有源/无源 are exposed as 机械设备/周转材料/其他 respectively.
        Only the latest successful batch per project is used so re-uploads do
        not double count a project's figures.
        """
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        projects = await query.order_by("id")
        total = len(projects)

        pids = [project.id for project in projects]
        batches = await TortoiseAnalyticsRepository._latest_batch_map(pids, ym)

        rows_by_batch: dict[int, list[DataBudgetLease]] = {}
        if batches:
            for row in await DataBudgetLease.filter(batch_id__in=[batch.id for batch in batches.values()]):
                rows_by_batch.setdefault(row.batch_id, []).append(row)

        items: list[dict[str, Any]] = []
        for project in projects:
            project_batch = batches.get(project.id)
            rows = rows_by_batch.get(project_batch.id, []) if project_batch else []

            lease_total = _sum_lease_rows(rows, "lease_total")
            writeoff_total = _sum_lease_rows(rows, "writeoff_total")
            item = {
                "project_id": project.id,
                "project_code": project.code,
                "project_name": project.name,
                "ym": project_batch.ym if project_batch else ym,
                "budget_lease_total": lease_total,
                "cumulative_lease": {
                    "machinery_equipment": _sum_lease_rows(rows, "lease_bid"),
                    "turnover_materials": _sum_lease_rows(rows, "lease_active"),
                    "other": _sum_lease_rows(rows, "lease_passive"),
                },
                "written_off_total": writeoff_total,
                "unwritten_off_total": round(lease_total - writeoff_total, 2),
                "remaining_lease": {
                    "machinery_equipment": _sum_lease_rows(rows, "remaining_bid"),
                    "turnover_materials": _sum_lease_rows(rows, "remaining_active"),
                    "other": _sum_lease_rows(rows, "remaining_passive"),
                },
            }
            items.append(item)

        def total_for(path: tuple[str, ...]) -> float:
            values = []
            for entry in items:
                value: Any = entry
                for key in path:
                    value = value[key]
                values.append(float(value))
            return round(sum(values), 2)

        summary = {
            "budget_lease_total": total_for(("budget_lease_total",)),
            "cumulative_lease": {
                "machinery_equipment": total_for(("cumulative_lease", "machinery_equipment")),
                "turnover_materials": total_for(("cumulative_lease", "turnover_materials")),
                "other": total_for(("cumulative_lease", "other")),
            },
            "written_off_total": total_for(("written_off_total",)),
            "unwritten_off_total": total_for(("unwritten_off_total",)),
            "remaining_lease": {
                "machinery_equipment": total_for(("remaining_lease", "machinery_equipment")),
                "turnover_materials": total_for(("remaining_lease", "turnover_materials")),
                "other": total_for(("remaining_lease", "other")),
            },
        }
        return {
            "summary": summary,
            "projects": items[pagination.offset : pagination.offset + pagination.size],
            "pagination": {
                "page": pagination.page,
                "size": pagination.size,
                "total": total,
            },
        }

    @staticmethod
    async def _load_batches(projects, ym):
        pids = [p.id for p in projects]
        batch_map = await TortoiseAnalyticsRepository._latest_batch_map(pids, ym)
        settlement_rows = await DataSettlementOutput.filter(batch_id__in=[b.id for b in batch_map.values()])
        profit_map = {}
        for row in settlement_rows:
            profit_map.setdefault(row.batch_id, {})[row.indicator_name] = row.cumulative_value
        # 指标（含税）口径来自 00 动态指标 sheet（data_dynamic_indicator）：
        # 预计完工成本取"预计完工量含税指标"合计，缺失时回退"清单量含税指标"。
        indicator_map = {}
        for row in await DataDynamicIndicator.filter(batch_id__in=[b.id for b in batch_map.values()]):
            value = row.estimated_with_tax
            if value is None:
                value = row.indicator_with_tax
            if value is None:
                continue
            indicator_map[row.batch_id] = indicator_map.get(row.batch_id, 0.0) + float(value)
        return batch_map, profit_map, indicator_map

    @staticmethod
    def _profit_item(project, batch_map, profit_map, indicator_map, ym) -> dict:
        batch = batch_map.get(project.id)
        indicators = profit_map.get(batch.id) if batch else None
        indicators = indicators or {}
        # Profit figures come from 表11 结算产值表 (data_settlement_output);
        # the old 毛利 sheet was retired and data_gross_profit dropped.
        revenue = _settle(indicators, SETTLE_CUMULATIVE_OUTPUT, SETTLE_CONTRACT_PRICE)
        profit = _settle(indicators, SETTLE_CURRENT_PROFIT)
        if indicators:
            cost = _settle(indicators, SETTLE_CUMULATIVE_COST)
        else:
            revenue = revenue or _number(project.contract_price)
            cost = revenue - profit
        f_rev = _settle(indicators, SETTLE_FORECAST_REVENUE) if indicators else revenue
        f_prf = _settle(indicators, SETTLE_FORECAST_PROFIT) if indicators else profit
        f_cost = _settle(indicators, SETTLE_FORECAST_COST) if indicators else f_rev - f_prf
        # 指标（含税）口径：预计完工成本取 00 动态指标 sheet 的含税指标合计，
        # 结算收入以表11 合同总价近似（工作簿无独立的指标收入列）。
        i_cost = indicator_map.get(batch.id) if batch else None
        if i_cost is not None:
            i_rev = _settle(indicators, SETTLE_CONTRACT_PRICE) or _number(project.contract_price)
            i_prf = round(i_rev - _number(i_cost), 2)
            indicator_block = {
                "revenue": i_rev,
                "cost": round(_number(i_cost), 2),
                "profit": i_prf,
                "profit_rate": _rate(i_prf, i_rev),
            }
        else:
            indicator_block = {"revenue": 0.0, "cost": 0.0, "profit": 0.0, "profit_rate": 0.0}
        # 投标口径在本工作簿中无数据源（投标总价在"报价表一"报价文件内），
        # bid 块保持结构但返回 0。
        return {
            "project_id": project.id,
            "project_code": project.code,
            "project_name": project.name,
            "ym": batch.ym if batch else ym,
            "bid": {"revenue": 0.0, "cost": 0.0, "profit": 0.0, "profit_rate": 0.0},
            "indicator": indicator_block,
            "current": {
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
                "profit_rate": _settle_rate(indicators, SETTLE_CURRENT_PROFIT_RATE, profit, revenue),
            },
            "forecast": {
                "revenue": f_rev,
                "cost": f_cost,
                "profit": f_prf,
                "profit_rate": _settle_rate(indicators, SETTLE_FORECAST_PROFIT_RATE, f_prf, f_rev),
            },
        }

    async def dashboard(self, project_ids: list[int] | None = None) -> dict:
        project_query = Project.all()
        if project_ids is not None:
            project_query = project_query.filter(id__in=project_ids)
        summary, profits, projects, trends, cost_composition = await asyncio.gather(
            self.project_summary(project_ids),
            self.project_profits(None, Pagination(1, 10_000, max_size=10_000), project_ids),
            project_query.order_by("id"),
            self.dashboard_trends(project_ids),
            self.cost_composition(project_ids),
        )
        status = [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "progress": _number(p.progress),
            }
            for p in projects
        ]
        total_profit = sum(item["current"]["profit"] for item in profits["projects"])
        return {
            "summary": {**summary, "total_profit": round(total_profit, 2)},
            "project_status": status,
            "profit_distribution": profits["projects"],
            "trends": trends,
            "cost_composition": cost_composition,
            "health_radar": self._health_radar_from_data(projects, profits["projects"]),
        }

    async def dashboard_summary(self, project_ids: list[int] | None = None) -> dict:
        """Lightweight summary for /dashboard/summary.

        The full dashboard() additionally computes trends, cost composition and
        the health radar — wasted work for callers that only read the summary.
        total_profit is the same per-project current-profit aggregation used by
        dashboard(), computed here without the sibling report queries.
        """
        summary = await self.project_summary(project_ids)
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        projects = await query.order_by("id")
        batch_map, profit_map, indicator_map = await self._load_batches(projects, None)
        total_profit = round(
            sum(
                self._profit_item(project, batch_map, profit_map, indicator_map, None)["current"]["profit"]
                for project in projects
            ),
            2,
        )
        return {**summary, "total_profit": total_profit}

    async def dashboard_status(
        self,
        project_ids: list[int] | None = None,
        pagination: Pagination | None = None,
    ) -> dict:
        """Paged project status rows for /dashboard/project-status.

        The full dashboard() projects every row then slices in Python; this
        pushes the LIMIT/OFFSET into SQL. Each row carries the project's
        current gross-profit rate (same _profit_item caliber as dashboard), so
        the dashboard "项目实时状态" list needs no second API call.
        """
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        total = await query.count()
        page = pagination or Pagination(1, 20, max_size=100)
        projects = await query.order_by("id").offset(page.offset).limit(page.size)
        batch_map, profit_map, indicator_map = await self._load_batches(projects, None)
        status = [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "progress": _number(p.progress),
                "profit_rate": self._profit_item(p, batch_map, profit_map, indicator_map, None)["current"][
                    "profit_rate"
                ],
            }
            for p in projects
        ]
        return {"projects": status, "pagination": {"page": page.page, "size": page.size, "total": total}}

    async def health_radar(self, project_ids: list[int] | None = None) -> dict:
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        projects = await query
        profits = await self.project_profits(None, Pagination(1, 10_000, max_size=10_000), project_ids)
        return self._health_radar_from_data(projects, profits["projects"])

    @staticmethod
    def _health_radar_from_data(projects: list[Project], profits: list[dict]) -> dict:
        if not projects:
            return {
                "dimensions": {
                    "progress": 0,
                    "cost": 0,
                    "quality": 0,
                    "safety": 0,
                    "efficiency": 0,
                    "profit": 0,
                }
            }
        rates = [max(0, min(100, item["current"]["profit_rate"] * 5)) for item in profits]

        def _avg(values):
            return round(sum(values) / len(values), 2) if values else 0

        warning_ratio = sum(p.status == "warning" for p in projects) / len(projects)
        progress = _avg([_number(p.progress) for p in projects])
        risk = round((1 - warning_ratio) * 100, 2)
        return {
            "dimensions": {
                "progress": progress,
                "cost": _avg([100 - min(100, abs(r - 80)) for r in rates]),
                # 当前工作簿没有独立质量/安全指标，使用项目无预警率作为透明兜底，
                # 字段先与 UI 六维雷达对齐，后续有专门数据源时可无损替换。
                "quality": risk,
                "safety": risk,
                "efficiency": progress,
                "profit": _avg(rates),
            }
        }

    async def dashboard_trends(self, project_ids: list[int] | None = None) -> list[dict]:
        base = UploadBatch.filter(status="success")
        if project_ids is not None:
            base = base.filter(project_id__in=project_ids)
        months = list(await base.order_by("-ym").distinct().values_list("ym", flat=True))[:12]
        batch_rows = await base.filter(ym__in=months).order_by("ym", "project_id", "-id") if months else []
        latest: dict[tuple[str, int], UploadBatch] = {}
        for batch in batch_rows:
            key = (batch.ym, batch.project_id)
            if key not in latest:
                latest[key] = batch
        batches = list(latest.values())
        data_by_batch = await self._monthly_data_maps([batch.id for batch in batches])
        batches_by_month: dict[str, list[UploadBatch]] = {}
        for batch in batches:
            batches_by_month.setdefault(batch.ym, []).append(batch)
        result = []
        for ym in reversed(months):
            revenue = cost = profit = 0.0
            for batch in batches_by_month.get(ym, []):
                item = self._monthly_item_from_data(
                    batch,
                    data_by_batch["settlement"].get(batch.id, []),
                    data_by_batch["dynamic"].get(batch.id, []),
                    data_by_batch["lease"].get(batch.id, []),
                )
                revenue += item["revenue"]
                cost += item["cost"]
                profit += item["profit"]
            result.append({"ym": ym, "revenue": round(revenue, 2), "cost": round(cost, 2), "profit": round(profit, 2)})
        return result

    async def cost_composition(self, project_ids: list[int] | None = None) -> list[dict]:
        totals: dict[str, float] = {}
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        projects = await query
        batch_map = await self._latest_batch_map([project.id for project in projects], None)
        batch_ids = [batch.id for batch in batch_map.values()]
        rows = await DataDynamicIndicator.filter(batch_id__in=batch_ids) if batch_ids else []
        for row in rows:
            name = row.item_name or "未分类"
            totals[name] = totals.get(name, 0.0) + _number(row.incurred_cost)
        return [
            {"name": name, "amount": round(amount, 2)}
            for name, amount in sorted(totals.items(), key=lambda item: -item[1])
        ]

    async def notifications(
        self, user_id: int, pagination: Pagination, unread_only: bool = False, project_ids: list[int] | None = None
    ) -> dict:
        query = Notification.filter(Q(user_id=user_id) | Q(user_id=None))
        if project_ids is not None:
            query = query.filter(Q(project_id__in=project_ids) | Q(project_id=None))
        # 已读集合用子查询而非全量拉取 ID 列表（原实现每请求把全部可见通知
        # 与全部已读 ID 拉进内存再做 exclude），通知量增长后不再线性膨胀。
        # 注意：Tortoise 1.1.7 的 __in 不接受未求值的 QuerySet，必须用 Subquery 包装。
        read_subquery = Subquery(
            NotificationRead.filter(user_id=user_id).values_list("notification_id", flat=True)
        )
        unread = await query.exclude(id__in=read_subquery).count()
        if unread_only:
            query = query.exclude(id__in=read_subquery)
        total = unread if unread_only else await query.count()
        rows = await query.order_by("-id").offset(pagination.offset).limit(pagination.size)
        read_ids = (
            set(
                await NotificationRead.filter(user_id=user_id, notification_id__in=[r.id for r in rows]).values_list(
                    "notification_id", flat=True
                )
            )
            if rows
            else set()
        )
        return {
            "notifications": [
                {
                    "id": row.id,
                    "type": row.notification_type,
                    "title": row.title,
                    "message": row.message,
                    "project_id": row.project_id,
                    "is_read": row.id in read_ids,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "unread": unread,
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def create_notification(self, data: dict) -> dict:
        async with self._tx.transaction():
            if not data.get("title") or not data.get("message"):
                raise ValidationError("title and message are required")
            row = await Notification.create(
                user_id=data.get("user_id"),
                notification_type=data.get("type", "system"),
                title=data["title"],
                message=data["message"],
                project_id=data.get("project_id"),
            )
            return {"id": row.id, "title": row.title}

    async def mark_notification_read(self, user_id: int, notification_id: int) -> None:
        async with self._tx.transaction():
            exists = await Notification.filter(id=notification_id).filter(Q(user_id=user_id) | Q(user_id=None)).exists()
            if not exists:
                raise NotFoundError(f"notification {notification_id} not found")
            await NotificationRead.get_or_create(
                notification_id=notification_id,
                user_id=user_id,
            )

    async def mark_all_notifications_read(self, user_id: int) -> int:
        """Mark every notification visible to the user (own + broadcast) as read.

        Returns the number of newly marked notifications (idempotent).
        """
        async with self._tx.transaction():
            all_ids = list(await Notification.filter(Q(user_id=user_id) | Q(user_id=None)).values_list("id", flat=True))
            if not all_ids:
                return 0
            read_ids = set(
                await NotificationRead.filter(
                    user_id=user_id,
                    notification_id__in=all_ids,
                ).values_list("notification_id", flat=True)
            )
            unread = [nid for nid in all_ids if nid not in read_ids]
            if unread:
                await NotificationRead.bulk_create(
                    [NotificationRead(notification_id=nid, user_id=user_id) for nid in unread],
                    ignore_conflicts=True,
                )
            return len(unread)

    async def delete_notification(self, user_id: int, notification_id: int) -> None:
        """Delete one of the user's OWN notifications.

        Broadcast notifications (user_id NULL) and other users' notifications
        are not deletable and surface as NotFoundError.
        """
        async with self._tx.transaction():
            deleted = await Notification.filter(
                id=notification_id,
                user_id=user_id,
            ).delete()
            if not deleted:
                raise NotFoundError(f"notification {notification_id} not found")
            await NotificationRead.filter(
                notification_id=notification_id,
                user_id=user_id,
            ).delete()

    async def clear_notifications(self, user_id: int) -> int:
        """Delete all of the user's OWN notifications; returns deleted count.

        Broadcast notifications (user_id NULL) belong to everyone and are kept.
        """
        async with self._tx.transaction():
            own_ids = list(
                await Notification.filter(
                    user_id=user_id,
                ).values_list("id", flat=True)
            )
            if not own_ids:
                return 0
            await NotificationRead.filter(
                notification_id__in=own_ids,
                user_id=user_id,
            ).delete()
            return await Notification.filter(id__in=own_ids).delete()

    async def ai_analysis(self, project_id: int, ym: str | None) -> dict:
        project = await self._project(project_id)
        profits = await self._profit_for(project_id, ym)
        batch = await self._batch(project_id, ym)
        monthly = await self._monthly_item(batch) if batch else None
        # Repository helpers return numeric rates, but keep the API resilient to
        # nullable/legacy rows: missing rates stay None so they are omitted from
        # the summary instead of being reported as a misleading 0.00%.
        rate = _number_or_none(profits.get("profit_rate"))
        forecast_rate = _number_or_none(monthly.get("expected_complete_profit_rate")) if monthly else None
        writeoff_rate = _number_or_none(monthly.get("write_off_rate")) if monthly else None
        if rate is None:
            health = "warning" if project.status == "warning" else "healthy"
            summary = f"项目状态为 {project.status}。"
        else:
            health = "warning" if project.status == "warning" or rate < 10 else "healthy"
            summary = f"当前毛利率为 {rate:.2f}%，项目状态为 {project.status}。"
        if forecast_rate is not None:
            summary += f"预计完工毛利率 {forecast_rate:.2f}%。"
        if writeoff_rate is not None:
            summary += f"租借核销率 {writeoff_rate:.2f}%。"
        fallback: dict[str, Any] = {
            "project_id": project_id,
            "ym": profits["ym"],
            "health": health,
            "summary": summary,
            "insights": [
                {
                    "type": "profit",
                    "title": "毛利率表现",
                    "message": (
                        f"当前毛利 {profits['profit']:.2f}，毛利率 {rate:.2f}%"
                        if rate is not None
                        else f"当前毛利 {profits['profit']:.2f}，毛利率数据缺失"
                    ),
                },
                {
                    "type": "progress",
                    "title": "项目进度",
                    "message": f"当前项目进度 {float(project.progress):.2f}%",
                },
            ],
            "recommendations": [
                "持续跟踪实际成本与执行预算偏差",
                "确保月度数据及时上传并完成异常项复核",
            ],
        }
        if writeoff_rate is not None:
            fallback["insights"].append(
                {
                    "type": "writeoff",
                    "title": "租借核销进度",
                    "message": f"当前核销率 {writeoff_rate:.2f}%",
                }
            )
        if self._ai_provider:
            try:
                result = await self._ai_provider.analyze(
                    {
                        "project": {
                            "id": project.id,
                            "name": project.name,
                            "status": project.status,
                            "progress": float(project.progress),
                        },
                        "period": profits["ym"],
                        "metrics": {**profits, "monthly": monthly},
                    }
                )
            except Exception:
                # 外部 AI 服务不可用时回退到本地确定性分析，而不是 500。
                logger.exception("AI analysis provider failed for project %s; using fallback", project_id)
                result = None
            if result:
                return {"project_id": project_id, "ym": profits["ym"], **result}
        return fallback

    async def compare_ai_analysis(self, project_ids: list[int] | None, ym: str | None) -> dict:
        """Multi-project AI report: five chapters aligned with the comparison UI.

        Uses the external provider when configured; otherwise falls back to the
        deterministic domain report built from compare metrics + scores.
        """
        comparison = await self.compare_projects(project_ids, ym)
        metrics = comparison["projects"]
        generated_at = datetime.now().isoformat(timespec="seconds")
        if self._ai_provider:
            try:
                result = await self._ai_provider.analyze(
                    {
                        "type": "project_comparison",
                        "period": ym,
                        "projects": metrics,
                    }
                )
            except Exception:
                # 外部 AI 服务不可用时回退到本地确定性五章报告，而不是 500。
                logger.exception("AI analysis provider failed for comparison; using fallback")
                result = None
            if result:
                return {"project_ids": project_ids, "ym": ym, "generated_at": generated_at, **result}
        return {
            "project_ids": project_ids,
            "ym": ym,
            "generated_at": generated_at,
            "projects": [
                {
                    "project_id": p["project_id"],
                    "project_name": p["project_name"],
                    "total_score": p["total_score"],
                    "grade": p["grade"],
                }
                for p in metrics
            ],
            "chapters": build_compare_report(metrics, ym),
        }

    async def global_search(
        self, keyword: str, pagination: Pagination, project_ids: list[int] | None = None, include_users: bool = True
    ) -> dict:
        keyword = keyword.strip()
        if not keyword:
            return {"results": [], "pagination": {"page": pagination.page, "size": pagination.size, "total": 0}}
        candidate_limit = pagination.offset + pagination.size
        project_query = Project.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
        if project_ids is not None:
            project_query = project_query.filter(id__in=project_ids)
        if include_users:
            user_query = User.filter(Q(real_name__icontains=keyword) | Q(email__icontains=keyword))
            project_total, user_total, projects, users = await asyncio.gather(
                project_query.count(),
                user_query.count(),
                project_query.order_by("name").limit(candidate_limit),
                user_query.order_by("real_name", "id").limit(candidate_limit),
            )
        else:
            users, user_total = [], 0
            project_total = await project_query.count()
            projects = await project_query.order_by("name").limit(candidate_limit)
        reports = [
            item for item in self._REPORT_CATALOG if keyword.lower() in (item["title"] + item["subtitle"]).lower()
        ]
        business_results, business_total = await self._business_search(
            keyword,
            project_ids,
            candidate_limit,
        )
        all_results = (
            [{"type": "project", "id": p.id, "title": p.name, "subtitle": p.code} for p in projects]
            + [
                {"type": "user", "id": u.id, "title": u.real_name or u.username, "subtitle": u.email or ""}
                for u in users
            ]
            + reports
            + business_results
        )
        all_results.sort(key=lambda item: (item["title"], item["type"], str(item["id"])))
        total = project_total + user_total + len(reports) + business_total
        return {
            "results": all_results[pagination.offset : pagination.offset + pagination.size],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    @staticmethod
    async def _business_search(keyword: str, project_ids: list[int] | None, limit: int) -> tuple[list[dict], int]:
        """Search parsed business data (materials / cost items / alerts).

        Data rows are scoped to the latest successful batch of each in-scope
        project so stale monthly batches do not produce duplicate hits.
        """
        batch_query = UploadBatch.filter(status="success")
        if project_ids is not None:
            batch_query = batch_query.filter(project_id__in=project_ids)
        batches = await batch_query.order_by("project_id", "-ym", "-id")
        latest: dict[int, int] = {}
        for b in batches:
            latest.setdefault(b.project_id, b.id)
        batch_ids = list(latest.values())
        if not batch_ids:
            return [], 0
        latest_ids = set(latest.values())
        batch_to_project = {b.id: b.project_id for b in batches if b.id in latest_ids}
        project_names = {p.id: p.name for p in await Project.filter(id__in=latest.keys())}

        alert_query = AlertModel.filter(Q(title__icontains=keyword) | Q(message__icontains=keyword))
        if project_ids is not None:
            alert_query = alert_query.filter(project_id__in=project_ids)

        search_results = await asyncio.gather(
            DataMaterialCost.filter(batch_id__in=batch_ids, budget_category__icontains=keyword).count(),
            DataConstructionDynamic.filter(batch_id__in=batch_ids, project_name__icontains=keyword).count(),
            DataInstallationDynamic.filter(batch_id__in=batch_ids, project_name__icontains=keyword).count(),
            alert_query.count(),
            DataMaterialCost.filter(batch_id__in=batch_ids, budget_category__icontains=keyword).limit(limit),
            DataConstructionDynamic.filter(batch_id__in=batch_ids, project_name__icontains=keyword).limit(limit),
            DataInstallationDynamic.filter(batch_id__in=batch_ids, project_name__icontains=keyword).limit(limit),
            alert_query.order_by("-last_triggered_at").limit(limit),
        )
        mat_total = cast(int, search_results[0])
        con_total = cast(int, search_results[1])
        inst_total = cast(int, search_results[2])
        alert_total = cast(int, search_results[3])
        materials = cast(list[DataMaterialCost], search_results[4])
        constructions = cast(list[DataConstructionDynamic], search_results[5])
        installations = cast(list[DataInstallationDynamic], search_results[6])
        alerts = cast(list[AlertModel], search_results[7])

        results: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add(type_: str, row_id: int, title: str | None, subtitle: str) -> None:
            if not title:
                return
            key = (type_, title)
            if key in seen:
                return
            seen.add(key)
            results.append({"type": type_, "id": row_id, "title": title, "subtitle": subtitle})

        def project_of(row) -> str:
            project_id = batch_to_project.get(int(row.batch_id))
            return project_names.get(project_id, "") if project_id is not None else ""

        for material in materials:
            suffix = f" · {material.unit}" if material.unit else ""
            add(
                "material",
                material.id,
                material.budget_category,
                f"{project_of(material)}{suffix}",
            )
        for construction in constructions:
            add(
                "cost_item",
                construction.id,
                construction.project_name,
                f"{project_of(construction)} · 建筑工程",
            )
        for installation in installations:
            add(
                "cost_item",
                installation.id,
                installation.project_name,
                f"{project_of(installation)} · 安装工程",
            )
        for alert in alerts:
            add(
                "alert",
                alert.id,
                alert.title,
                f"{alert.level} · {alert.status}",
            )
        return results, mat_total + con_total + inst_total + alert_total

    async def sync_status(self) -> dict:
        latest = await UploadBatch.all().order_by("-created_at").first()
        return {
            "status": "ok",
            "latest_month": latest.ym if latest else None,
            "last_synced_at": latest.created_at.isoformat() if latest else None,
        }

    async def _monthly_item(self, batch: UploadBatch) -> dict:
        settlement_rows, dynamic_rows, lease_rows = await asyncio.gather(
            DataSettlementOutput.filter(batch_id=batch.id),
            DataDynamicIndicator.filter(batch_id=batch.id),
            DataBudgetLease.filter(batch_id=batch.id),
        )
        return self._monthly_item_from_data(batch, settlement_rows, dynamic_rows, lease_rows)

    @staticmethod
    def _monthly_item_from_data(
        batch: UploadBatch,
        settlement_rows: list[DataSettlementOutput],
        dynamic_rows: list[DataDynamicIndicator],
        lease_rows: list[DataBudgetLease],
    ) -> dict:
        indicators = settlement_indicator_map(settlement_rows)
        # 毛利数据自 表11 结算产值表读取（旧毛利 sheet 已随远端重构废弃）。
        revenue = _settle(indicators, SETTLE_CUMULATIVE_OUTPUT, SETTLE_CONTRACT_PRICE)
        profit = _settle(indicators, SETTLE_CURRENT_PROFIT)
        cost = _settle(indicators, SETTLE_CUMULATIVE_COST) if indicators else revenue - profit
        # 预计完工组：回退约定与 _profit_item forecast 组一致。
        f_rev = _settle(indicators, SETTLE_FORECAST_REVENUE)
        f_prf = _settle(indicators, SETTLE_FORECAST_PROFIT)
        f_cost = _settle(indicators, SETTLE_FORECAST_COST) if indicators else f_rev - f_prf
        target_rows = [row for row in dynamic_rows if str(row.item_name or "").startswith("项目成本合计")]
        if not target_rows:
            target_rows = [row for row in dynamic_rows if "一级" in str(row.display_level or "")]
        if not target_rows:
            # Migration 0008 leaves historical display_level values NULL.
            # Recover only reliable top-level rows from the stored hierarchy
            # instead of summing parents and children together.
            legacy_hierarchy: list[dict[str, Any]] = [
                {"hierarchy_code": row.hierarchy_code, "row": row}
                for row in dynamic_rows
                if row.item_name and row.hierarchy_code
            ]
            resolve_hierarchy_paths(legacy_hierarchy)
            target_rows = [
                cast(DataDynamicIndicator, item["row"]) for item in legacy_hierarchy if item.get("level") == 1
            ]
        target_cost = round(sum(_number(row.indicator_with_tax) for row in target_rows), 2) if target_rows else None
        contract = _settle(indicators, SETTLE_CONTRACT_PRICE)
        target_profit = round(contract - target_cost, 2) if target_cost is not None else None
        lease_total = round(sum(_number(row.lease_total) for row in lease_rows), 2)
        written_off = round(sum(_number(row.writeoff_total) for row in lease_rows), 2)
        rental_profit = round(lease_total - written_off, 2) if lease_rows else None
        return {
            "batch_id": batch.id,
            "ym": batch.ym,
            "file_name": batch.file_name,
            "status": batch.status,
            "uploaded_at": batch.created_at.isoformat(),
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "profit_rate": _settle_rate(indicators, SETTLE_CURRENT_PROFIT_RATE, profit, revenue),
            # ── 基础指标 ──
            "contract_price": contract,
            "estimated_completion_price": f_rev,
            "target_profit": target_profit,
            "target_profit_rate": (_rate(target_profit, contract) if target_profit is not None else None),
            # ── 预计完工指标 ──
            "expected_complete_settlement": f_rev,
            "expected_complete_cost": f_cost,
            "expected_complete_profit": f_prf,
            "expected_complete_profit_rate": _settle_rate(indicators, SETTLE_FORECAST_PROFIT_RATE, f_prf, f_rev),
            # ── 租借及核销（表10.3）──
            # UI 的结算/成本/毛利对应租借总额/已核销/未核销。
            "rental_expected_settlement": lease_total if lease_rows else None,
            "rental_cost": written_off if lease_rows else None,
            "rental_profit": rental_profit,
            "write_off_rate": (round(written_off / lease_total * 100, 2) if lease_total else None),
        }

    @staticmethod
    async def _monthly_data_maps(batch_ids: list[int]) -> dict[str, dict[int, list]]:
        result: dict[str, dict[int, list]] = {
            "settlement": {},
            "dynamic": {},
            "lease": {},
        }
        if not batch_ids:
            return result
        settlement_rows, dynamic_rows, lease_rows = await asyncio.gather(
            DataSettlementOutput.filter(batch_id__in=batch_ids),
            DataDynamicIndicator.filter(batch_id__in=batch_ids),
            DataBudgetLease.filter(batch_id__in=batch_ids),
        )
        for key, rows in (
            ("settlement", settlement_rows),
            ("dynamic", dynamic_rows),
            ("lease", lease_rows),
        ):
            grouped = result[key]
            for row in rows:
                grouped.setdefault(row.batch_id, []).append(row)
        return result

    async def _profit_for(self, project_id: int, ym: str | None) -> dict:
        batch = await self._batch(project_id, ym)
        indicators = {}
        if batch is not None:
            rows = await DataSettlementOutput.filter(batch_id=batch.id)
            indicators = settlement_indicator_map(rows)
        revenue = _settle(indicators, SETTLE_CUMULATIVE_OUTPUT, SETTLE_CONTRACT_PRICE)
        profit = _settle(indicators, SETTLE_CURRENT_PROFIT)
        return {
            "ym": batch.ym if batch else ym,
            "profit": profit,
            "profit_rate": _settle_rate(indicators, SETTLE_CURRENT_PROFIT_RATE, profit, revenue),
        }

    @staticmethod
    async def _batch(project_id: int, ym: str | None):
        return (await TortoiseAnalyticsRepository._latest_batch_map([project_id], ym)).get(project_id)

    @staticmethod
    async def _latest_batch_map(project_ids: list[int], ym: str | None) -> dict[int, UploadBatch]:
        if not project_ids:
            return {}
        query = UploadBatch.filter(project_id__in=project_ids, status="success")
        if ym:
            query = query.filter(ym=ym)
        result: dict[int, UploadBatch] = {}
        for batch in await query.order_by("project_id", "-ym", "-id"):
            if batch.project_id not in result:
                result[batch.project_id] = batch
        return result

    @staticmethod
    async def _project(project_id: int):
        project = await Project.get_or_none(id=project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    @staticmethod
    def _milestone(row) -> dict:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "ym": row.ym,
            "progress": _number(row.progress),
            "title": row.title,
            "description": row.description or "",
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
