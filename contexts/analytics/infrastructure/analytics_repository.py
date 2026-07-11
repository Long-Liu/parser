from __future__ import annotations

from decimal import Decimal

from tortoise.transactions import atomic

from contexts.auth.infrastructure.tables import User
from contexts.auth.infrastructure.tables import Notification, NotificationRead
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.parsing.infrastructure.tables import UploadLog
from contexts.project.infrastructure.tables import Project
from contexts.project.infrastructure.tables import ProjectMilestone
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.database.tables import (
    DataDynamicIndicator,
    DataGrossProfit,
)
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS
from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.analytics.domain.repositories import AnalyticsRepository


def _number(value) -> float:
    return float(value) if value is not None else 0.0


def _or_default(value, default):
    """Return value if it is not None, otherwise default. Unlike `or`, treats 0/0.0/Decimal('0') as real values."""
    return value if value is not None else default


def _rate(profit: float, revenue: float) -> float:
    return round(profit / revenue * 100, 2) if revenue else 0.0


class TortoiseAnalyticsRepository(AnalyticsRepository):
    def __init__(self, ai_provider: AIAnalysisPort | None = None) -> None:
        self._ai_provider = ai_provider

    async def project_summary(self, project_ids: list[int] | None = None) -> dict:
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        total = await query.count()
        normal = await query.filter(status="normal").count()
        warning = await query.filter(status="warning").count()
        prices = sum(
            (value or Decimal("0") for value in await query.values_list(
                "contract_price", flat=True
            )),
            Decimal("0"),
        )
        return {
            "total": total,
            "normal": normal,
            "warning": warning,
            "contract_total": float(prices),
        }

    async def monthly_data(self, project_id: int, page: int, size: int) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        await self._project(project_id)
        months = list(await UploadBatch.filter(
            project_id=project_id, status="success",
        ).order_by("-ym").distinct().values_list("ym", flat=True))
        total = len(months)
        selected = months[(page - 1) * size:page * size]
        items = []
        for ym in selected:
            batch = await UploadBatch.filter(
                project_id=project_id, status="success", ym=ym,
            ).order_by("-id").first()
            if batch:
                items.append(await self._monthly_item(batch))
        return {"data": items, "pagination": {"page": page, "size": size, "total": total}}

    async def month_comparison(self, project_id: int, months: list[str]) -> dict:
        await self._project(project_id)
        if len(set(months)) < 2:
            raise ValidationError("at least two months are required")
        batches = await UploadBatch.filter(
            project_id=project_id, ym__in=list(set(months)), status="success",
        ).order_by("ym", "-id")
        seen = set()
        items = []
        for batch in batches:
            if batch.ym in seen:
                continue
            seen.add(batch.ym)
            items.append(await self._monthly_item(batch))
        return {"project_id": project_id, "months": items}

    async def compare_projects(self, project_ids: list[int], ym: str | None) -> dict:
        if len(set(project_ids)) < 2:
            raise ValidationError("at least two projects are required")
        costs = await self.cost_categories(project_ids, ym, 1, 100)
        profits = await self._profits_for_ids(project_ids, ym)
        return {"cost_categories": costs["projects"], "profits": profits}

    @atomic()
    async def delete_monthly_data(self, project_id: int, ym: str) -> None:
        await self._project(project_id)
        batches = await UploadBatch.filter(project_id=project_id, ym=ym)
        batch_ids = [batch.id for batch in batches]
        if not batch_ids:
            raise NotFoundError(f"monthly data {ym} not found")
        for model in TEMPLATE_DATA_MODELS.values():
            await model.filter(batch_id__in=batch_ids).delete()
        await UploadLog.filter(batch_id__in=batch_ids).delete()
        await UploadBatch.filter(id__in=batch_ids).delete()
        # Clean up any preview records for these batches
        from contexts.parsing.infrastructure.tables import UploadPreview
        await UploadPreview.filter(batch_id__in=batch_ids).delete()

    async def cost_categories(self, project_ids: list[int], ym: str | None,
                              page: int = 1, size: int = 20) -> dict:
        pagination = Pagination(page, size, max_size=100)
        projects = await Project.filter(id__in=project_ids).order_by("id") if project_ids else await Project.all().order_by("id")
        series = []
        totals = []
        for project in projects:
            batch = await self._batch(project.id, ym)
            query = DataDynamicIndicator.filter(batch_id=batch.id) if batch else None
            total = await query.count() if query else 0
            totals.append(total)
            rows = [] if query is None else await query.order_by("id").offset(
                pagination.offset
            ).limit(pagination.size)
            series.append({
                "project": {"id": project.id, "code": project.code, "name": project.name},
                "ym": batch.ym if batch else ym,
                "items": [{
                    "hierarchy_code": row.hierarchy_code,
                    "name": row.item_name,
                    "indicator": _number(row.indicator_with_tax),
                    "actual": _number(row.incurred_cost),
                    "deviation": round(_number(row.incurred_cost) - _number(row.indicator_with_tax), 2),
                    "deviation_rate": _rate(
                        _number(row.incurred_cost) - _number(row.indicator_with_tax),
                        _number(row.indicator_with_tax),
                    ),
                } for row in rows],
            })
        return {"projects": series,
                "pagination": {"page": page, "size": size,
                               "total": max(totals, default=0)}}

    async def cost_details(self, project_id: int, ym: str | None,
                           page: int, size: int) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        result = await self.cost_categories([project_id], ym, page, size)
        if not result["projects"]:
            raise NotFoundError(f"project {project_id} not found")
        project = result["projects"][0]
        rows = project["items"]
        return {"project": project["project"], "ym": project["ym"],
                "data": rows, "pagination": result["pagination"]}

    async def project_analysis(self, project_id: int, ym: str | None) -> dict:
        project = await self._project(project_id)
        profit = await self._profit_for(project_id, ym)
        cost = await self.cost_details(project_id, ym, 1, 100)
        return {
            "project": {"id": project.id, "code": project.code, "name": project.name,
                        "status": project.status, "progress": _number(project.progress),
                        "contract_price": _number(project.contract_price)},
            "ym": cost["ym"], "profit": profit, "cost_categories": cost["data"],
            "milestones": (await self.milestones(project_id, 1, 100))["milestones"],
        }

    async def milestones(self, project_id: int, page: int, size: int) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        await self._project(project_id)
        query = ProjectMilestone.filter(project_id=project_id)
        total = await query.count()
        rows = await query.order_by("-ym", "-id").offset((page - 1) * size).limit(size)
        return {"milestones": [self._milestone(row) for row in rows],
                "pagination": {"page": page, "size": size, "total": total}}

    async def project_progress(self, project_id: int, page: int, size: int) -> dict:
        result = await self.milestones(project_id, page, size)
        return {
            "progress": [{
                "id": row["id"], "ym": row["ym"], "progress": row["progress"],
                "completion": row["description"], "latest_milestone": row["title"],
                "completed_at": row["completed_at"],
            } for row in result["milestones"]],
            "pagination": result["pagination"],
        }

    @atomic()
    async def create_milestone(self, project_id: int, data: dict) -> dict:
        await self._project(project_id)
        if not data.get("ym") or not data.get("title"):
            raise ValidationError("ym and title are required")
        row = await ProjectMilestone.create(
            project_id=project_id, ym=data["ym"], title=data["title"].strip(),
            progress=Decimal(str(data.get("progress", 0))),
            description=data.get("description", ""),
            completed_at=data.get("completed_at") or None,
        )
        return self._milestone(row)

    @atomic()
    async def update_milestone(self, project_id: int, milestone_id: int,
                               data: dict) -> dict:
        row = await ProjectMilestone.get_or_none(
            id=milestone_id, project_id=project_id,
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

    @atomic()
    async def delete_milestone(self, project_id: int, milestone_id: int) -> None:
        deleted = await ProjectMilestone.filter(
            id=milestone_id, project_id=project_id,
        ).delete()
        if not deleted:
            raise NotFoundError(f"milestone {milestone_id} not found")

    async def project_profits(self, ym: str | None, page: int, size: int,
                              project_ids: list[int] | None = None) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        total = await query.count()
        projects = await query.order_by("id").offset((page - 1) * size).limit(size)
        project_ids = [project.id for project in projects]
        batch_query = UploadBatch.filter(
            project_id__in=project_ids, status="success",
        )
        if ym:
            batch_query = batch_query.filter(ym=ym)
        batches = await batch_query.order_by("project_id", "-ym", "-id")
        latest_batches = {}
        for batch in batches:
            latest_batches.setdefault(batch.project_id, batch)
        profits = {
            row.batch_id: row
            for row in await DataGrossProfit.filter(
                batch_id__in=[batch.id for batch in latest_batches.values()]
            )
        }
        items = []
        for project in projects:
            batch = latest_batches.get(project.id)
            row = profits.get(batch.id) if batch else None
            revenue = _number(_or_default(row.actual_revenue, row.contract_price)) if row else _number(project.contract_price)
            profit = _number(_or_default(row.actual_profit, row.gross_profit_net)) if row else 0.0
            cost = _number(row.actual_cost) if row and row.actual_cost is not None else revenue - profit
            forecast_revenue = _number(_or_default(row.forecast_revenue, row.estimated_completion_price)) if row else revenue
            forecast_profit = _number(_or_default(row.forecast_profit, row.estimated_gross_profit_net)) if row else profit
            bid_revenue = _number(_or_default(row.bid_revenue, row.contract_price)) if row else revenue
            bid_profit = _number(_or_default(row.bid_profit, row.gross_profit_total)) if row else 0.0
            indicator_revenue = _number(_or_default(row.indicator_revenue, row.contract_price)) if row else revenue
            indicator_profit = _number(_or_default(row.indicator_profit, row.gross_profit_net)) if row else 0.0
            items.append({
                "project_id": project.id, "project_code": project.code,
                "project_name": project.name, "ym": batch.ym if batch else ym,
                "bid": {"revenue": bid_revenue,
                        "cost": _number(row.bid_cost) if row and row.bid_cost is not None else bid_revenue - bid_profit,
                        "profit": bid_profit, "profit_rate": _rate(bid_profit, bid_revenue)},
                "indicator": {"revenue": indicator_revenue,
                              "cost": _number(row.indicator_cost) if row and row.indicator_cost is not None else indicator_revenue - indicator_profit,
                              "profit": indicator_profit,
                              "profit_rate": _rate(indicator_profit, indicator_revenue)},
                "current": {"revenue": revenue, "cost": cost, "profit": profit,
                            "profit_rate": _rate(profit, revenue)},
                "forecast": {"revenue": forecast_revenue,
                             "cost": forecast_revenue - forecast_profit,
                             "profit": forecast_profit,
                             "profit_rate": _rate(forecast_profit, forecast_revenue)},
            })
        return {"projects": items, "pagination": {"page": page, "size": size, "total": total}}

    async def dashboard(self, project_ids: list[int] | None = None) -> dict:
        summary = await self.project_summary(project_ids)
        profits = await self.project_profits(None, 1, 100, project_ids)
        project_query = Project.all()
        if project_ids is not None:
            project_query = project_query.filter(id__in=project_ids)
        status = [{
            "id": p.id, "name": p.name, "status": p.status,
            "progress": _number(p.progress),
        } for p in await project_query.order_by("id")]
        total_profit = sum(item["current"]["profit"] for item in profits["projects"])
        return {"summary": {**summary, "total_profit": round(total_profit, 2)},
                "project_status": status, "profit_distribution": profits["projects"],
                "trends": await self.dashboard_trends(project_ids),
                "cost_composition": await self.cost_composition(project_ids),
                "health_radar": await self.health_radar(project_ids)}

    async def health_radar(self, project_ids: list[int] | None = None) -> dict:
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        projects = await query
        if not projects:
            return {"dimensions": {"profit": 0, "cost": 0, "progress": 0,
                                    "schedule": 0, "risk": 0}}
        profits = await self.project_profits(None, 1, 100, project_ids)
        rates = [max(0, min(100, item["current"]["profit_rate"] * 5))
                 for item in profits["projects"]]
        avg = lambda values: round(sum(values) / len(values), 2) if values else 0
        warning_ratio = sum(p.status == "warning" for p in projects) / len(projects)
        progress = avg([_number(p.progress) for p in projects])
        return {"dimensions": {
            "profit": avg(rates), "cost": avg([100 - min(100, abs(r - 80)) for r in rates]),
            "progress": progress, "schedule": progress,
            "risk": round((1 - warning_ratio) * 100, 2),
        }}

    async def dashboard_trends(self, project_ids: list[int] | None = None) -> list[dict]:
        base = UploadBatch.filter(status="success")
        if project_ids is not None:
            base = base.filter(project_id__in=project_ids)
        months = list(await base.order_by(
            "-ym"
        ).distinct().values_list("ym", flat=True))[:12]
        result = []
        for ym in reversed(months):
            batches = await base.filter(ym=ym)
            revenue = cost = profit = 0.0
            for batch in batches:
                item = await self._monthly_item(batch)
                revenue += item["revenue"]
                cost += item["cost"]
                profit += item["profit"]
            result.append({"ym": ym, "revenue": round(revenue, 2),
                           "cost": round(cost, 2), "profit": round(profit, 2)})
        return result

    async def cost_composition(self, project_ids: list[int] | None = None) -> list[dict]:
        totals: dict[str, float] = {}
        query = Project.all()
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        for project in await query:
            batch = await self._batch(project.id, None)
            if batch is None:
                continue
            for row in await DataDynamicIndicator.filter(batch_id=batch.id):
                name = row.item_name or "未分类"
                totals[name] = totals.get(name, 0.0) + _number(row.incurred_cost)
        return [{"name": name, "amount": round(amount, 2)}
                for name, amount in sorted(totals.items(), key=lambda item: -item[1])]

    async def alerts(self, page: int, size: int,
                     project_ids: list[int] | None = None) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        query = Project.filter(status="warning")
        if project_ids is not None:
            query = query.filter(id__in=project_ids)
        total = await query.count()
        rows = await query.order_by("id").offset((page - 1) * size).limit(size)
        return {"alerts": [{"type": "project_warning", "project_id": p.id,
                            "title": p.name, "message": "项目处于预警状态"} for p in rows],
                "pagination": {"page": page, "size": size, "total": total}}

    async def notifications(self, user_id: int, page: int, size: int,
                            unread_only: bool = False,
                            project_ids: list[int] | None = None) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        from tortoise.expressions import Q
        query = Notification.filter(Q(user_id=user_id) | Q(user_id=None))
        if project_ids is not None:
            query = query.filter(Q(project_id__in=project_ids) | Q(project_id=None))
        all_ids = list(await query.values_list("id", flat=True))
        read_ids = set(await NotificationRead.filter(
            user_id=user_id, notification_id__in=all_ids,
        ).values_list("notification_id", flat=True)) if all_ids else set()
        if unread_only:
            query = query.exclude(id__in=list(read_ids))
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * size).limit(size)
        return {"notifications": [{"id": row.id, "type": row.notification_type,
                                    "title": row.title, "message": row.message,
                                    "project_id": row.project_id,
                                    "is_read": row.id in read_ids,
                                    "created_at": row.created_at.isoformat()} for row in rows],
                "unread": len(all_ids) - len(read_ids),
                "pagination": {"page": page, "size": size, "total": total}}

    @atomic()
    async def create_notification(self, data: dict) -> dict:
        if not data.get("title") or not data.get("message"):
            raise ValidationError("title and message are required")
        row = await Notification.create(
            user_id=data.get("user_id"),
            notification_type=data.get("type", "system"),
            title=data["title"], message=data["message"],
            project_id=data.get("project_id"),
        )
        return {"id": row.id, "title": row.title}

    @atomic()
    async def mark_notification_read(self, user_id: int, notification_id: int) -> None:
        from tortoise.expressions import Q
        exists = await Notification.filter(id=notification_id).filter(
            Q(user_id=user_id) | Q(user_id=None)
        ).exists()
        if not exists:
            raise NotFoundError(f"notification {notification_id} not found")
        await NotificationRead.get_or_create(
            notification_id=notification_id, user_id=user_id,
        )

    async def ai_analysis(self, project_id: int, ym: str | None) -> dict:
        project = await self._project(project_id)
        profits = await self._profit_for(project_id, ym)
        rate = profits["profit_rate"]
        health = "warning" if project.status == "warning" or rate < 10 else "healthy"
        fallback = {
            "project_id": project_id, "ym": profits["ym"], "health": health,
            "summary": f"当前毛利率为 {rate:.2f}%，项目状态为 {project.status}。",
            "insights": [
                {"type": "profit", "message": f"当前毛利 {profits['profit']:.2f}，毛利率 {rate:.2f}%"},
                {"type": "progress", "message": f"当前项目进度 {float(project.progress):.2f}%"},
            ],
            "recommendations": [
                "持续跟踪实际成本与执行预算偏差",
                "确保月度数据及时上传并完成异常项复核",
            ],
        }
        if self._ai_provider:
            result = await self._ai_provider.analyze({
                "project": {"id": project.id, "name": project.name,
                            "status": project.status,
                            "progress": float(project.progress)},
                "period": profits["ym"], "metrics": profits,
            })
            if result:
                return {"project_id": project_id, "ym": profits["ym"], **result}
        return fallback

    async def global_search(self, keyword: str, page: int, size: int,
                            project_ids: list[int] | None = None,
                            include_users: bool = True) -> dict:
        Pagination(page, size, max_size=100)  # validates, then discarded — side-effect free
        keyword = keyword.strip()
        from tortoise.expressions import Q
        limit = size
        offset = (page - 1) * size
        if not keyword:
            return {"results": [],
                    "pagination": {"page": page, "size": size, "total": 0}}
        candidate_limit = offset + limit
        project_query = Project.filter(
            Q(name__icontains=keyword) | Q(code__icontains=keyword)
        )
        if project_ids is not None:
            project_query = project_query.filter(id__in=project_ids)
        project_total = await project_query.count()
        projects = await project_query.order_by("name").limit(candidate_limit)
        users, user_total = [], 0
        if include_users:
            user_query = User.filter(
                Q(real_name__icontains=keyword) | Q(email__icontains=keyword)
            )
            user_total = await user_query.count()
            users = await user_query.order_by("real_name", "id").limit(candidate_limit)
        report_catalog = [
            {"type": "report", "id": "cost-categories", "title": "成本科目", "subtitle": "多项目成本对比"},
            {"type": "report", "id": "project-profits", "title": "项目毛利情况", "subtitle": "项目盈利分析"},
            {"type": "report", "id": "dashboard", "title": "数据大屏", "subtitle": "经营监控中心"},
        ]
        reports = [item for item in report_catalog
                   if keyword.lower() in (item["title"] + item["subtitle"]).lower()]
        all_results = ([{"type": "project", "id": p.id, "title": p.name, "subtitle": p.code} for p in projects]
                   + [{"type": "user", "id": u.id, "title": u.real_name or u.username,
                       "subtitle": u.email or ""} for u in users] + reports)
        all_results.sort(key=lambda item: (item["title"], item["type"], str(item["id"])))
        results = all_results[offset:offset + limit]
        total = project_total + user_total + len(reports)
        return {"results": results,
                "pagination": {"page": page, "size": size, "total": total}}

    async def sync_status(self) -> dict:
        latest = await UploadBatch.all().order_by("-created_at").first()
        return {"status": "ok", "latest_month": latest.ym if latest else None,
                "last_synced_at": latest.created_at.isoformat() if latest else None}

    async def _monthly_item(self, batch: UploadBatch) -> dict:
        row = await DataGrossProfit.filter(batch_id=batch.id).first()
        revenue = _number(row.contract_price) if row else 0.0
        profit = _number(row.gross_profit_net) if row else 0.0
        cost = revenue - profit
        return {"batch_id": batch.id, "ym": batch.ym, "file_name": batch.file_name,
                "status": batch.status, "uploaded_at": batch.created_at.isoformat(),
                "revenue": revenue, "cost": cost, "profit": profit,
                "profit_rate": _rate(profit, revenue)}

    async def _profit_for(self, project_id: int, ym: str | None) -> dict:
        batch = await self._batch(project_id, ym)
        row = None if batch is None else await DataGrossProfit.filter(batch_id=batch.id).first()
        revenue = _number(row.contract_price) if row else 0.0
        profit = _number(row.gross_profit_net) if row else 0.0
        return {"ym": batch.ym if batch else ym, "profit": profit,
                "profit_rate": _rate(profit, revenue)}

    async def _profits_for_ids(self, project_ids: list[int], ym: str | None) -> list[dict]:
        result = []
        for project in await Project.filter(id__in=project_ids).order_by("id"):
            profit = await self._profit_for(project.id, ym)
            result.append({"project_id": project.id, "project_name": project.name, **profit})
        return result

    @staticmethod
    async def _batch(project_id: int, ym: str | None):
        query = UploadBatch.filter(project_id=project_id, status="success")
        if ym:
            query = query.filter(ym=ym)
        return await query.order_by("-ym", "-id").first()

    @staticmethod
    async def _project(project_id: int):
        project = await Project.get_or_none(id=project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    @staticmethod
    def _milestone(row) -> dict:
        return {"id": row.id, "project_id": row.project_id, "ym": row.ym,
                "progress": _number(row.progress), "title": row.title,
                "description": row.description or "",
                "completed_at": row.completed_at.isoformat() if row.completed_at else None}
