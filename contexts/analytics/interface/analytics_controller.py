from __future__ import annotations

import io

from openpyxl import Workbook
from sanic.response import raw

from contexts.analytics.application.analytics_service import AnalyticsApplicationService
from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.auth.interface.auth_middleware import (
    require_auth,
    require_permission,
    require_project_access,
)
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from
from contexts.shared.interface.rest_controller import rest_controller


def _xlsx(workbook: Workbook, filename: str):
    output = io.BytesIO()
    workbook.save(output)
    return raw(output.getvalue(), content_type=(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ), headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@rest_controller("/api")
class AnalyticsController(BaseController):
    name = "analytics"

    def __init__(
        self,
        analytics_analytics_svc: AnalyticsApplicationService,
        access_policy: ProjectAccessPolicy,
        alert_svc: AlertApplicationService,
    ):
        super().__init__()
        self.analytics_svc = analytics_analytics_svc
        self.access_policy = access_policy
        self.alert_svc = alert_svc

    async def _project_scope(
        self, request, requested: list[int] | None = None
    ) -> list[int] | None:
        permissions = set(request.ctx.permissions or set())
        if "admin:roles" in permissions or "user:manage" in permissions:
            return requested
        accessible = set(
            await self.access_policy.accessible_project_ids(UserId(request.ctx.user_id))
        )
        if requested is None:
            return sorted(accessible)
        denied = set(requested) - accessible
        if denied:
            from contexts.shared.domain.exceptions import AuthorizationError

            raise AuthorizationError(f"no access to projects: {sorted(denied)}")
        return requested

    def setup(self):
        r = self.bp.add_route
        r(self.summary,             "/projects/summary",                    methods=["GET"])
        r(self.monthly_data,        "/projects/<project_id:int>/monthly-data", methods=["GET"])
        r(self.project_progress,    "/projects/<project_id:int>/progress",   methods=["GET"])
        r(self.milestones,          "/projects/<project_id:int>/milestones", methods=["GET"])
        r(self.create_milestone,    "/projects/<project_id:int>/milestones", methods=["POST"])
        r(self.update_milestone,    "/projects/<project_id:int>/milestones/<milestone_id:int>", methods=["PUT"])
        r(self.delete_milestone,    "/projects/<project_id:int>/milestones/<milestone_id:int>", methods=["DELETE"])
        r(self.cost_details,        "/projects/<project_id:int>/cost-details", methods=["GET"])
        r(self.project_analysis,    "/projects/<project_id:int>/analysis",   methods=["GET"])
        r(self.month_comparison,    "/projects/<project_id:int>/month-comparison", methods=["POST"])
        r(self.delete_monthly_data, "/projects/<project_id:int>/monthly-data/<ym:str>", methods=["DELETE"])
        r(self.compare_projects,    "/projects/compare",                    methods=["POST"])
        r(self.cost_categories,     "/reports/cost-categories",             methods=["GET"])
        r(self.project_profits,     "/reports/project-profits",             methods=["GET"])
        r(self.dashboard,           "/dashboard",                           methods=["GET"])
        r(self.dashboard_summary,   "/dashboard/summary",                   methods=["GET"])
        r(self.dashboard_trends,    "/dashboard/trends",                    methods=["GET"])
        r(self.dashboard_cost,      "/dashboard/cost-composition",          methods=["GET"])
        r(self.dashboard_health,    "/dashboard/health",                    methods=["GET"])
        r(self.dashboard_status,    "/dashboard/project-status",            methods=["GET"])
        r(self.dashboard_alerts,    "/dashboard/alerts",                    methods=["GET"])
        r(self.notifications,       "/notifications",                       methods=["GET"])
        r(self.create_notification, "/notifications",                       methods=["POST"])
        r(self.mark_read,           "/notifications/<notification_id:int>/read", methods=["PUT"])
        r(self.ai_analysis,         "/projects/<project_id:int>/ai-analysis", methods=["POST"])
        r(self.global_search,       "/search",                              methods=["GET"])
        r(self.sync_status,         "/system/sync-status",                  methods=["GET"])
        r(self.export_profits,      "/reports/project-profits/export",      methods=["GET"])
        r(self.export_costs,        "/reports/cost-categories/export",      methods=["GET"])
        r(self.export_project,      "/projects/<project_id:int>/export",    methods=["GET"])

    # ── project endpoints ──────────────────────────────────────────────

    @require_auth
    @require_permission("project:view")
    async def summary(self, request):
        return self.json(
            await self.analytics_svc.project_summary(await self._project_scope(request))
        )

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def monthly_data(self, request, project_id: int):
            return self.json(await self.analytics_svc.monthly_data(project_id, pagination_from(request)))

    @require_auth
    @require_permission("project:view")
    @require_project_access()
    async def project_progress(self, request, project_id: int):
            return self.json(await self.analytics_svc.project_progress(project_id, pagination_from(request)))

    @require_auth
    @require_permission("project:view")
    @require_project_access()
    async def milestones(self, request, project_id: int):
            return self.json(await self.analytics_svc.milestones(project_id, pagination_from(request)))

    @require_auth
    @require_permission("project:create")
    @require_project_access(roles={"manager"})
    async def create_milestone(self, request, project_id: int):
        try:
            return self.json(await self.analytics_svc.create_milestone(project_id, request.json or {}), status=201)
        except ValueError:
            raise ValidationError("invalid milestone values") from None

    @require_auth
    @require_permission("project:create")
    @require_project_access(roles={"manager"})
    async def update_milestone(self, request, project_id: int, milestone_id: int):
        try:
            return self.json(await self.analytics_svc.update_milestone(
                project_id, milestone_id, request.json or {},
            ))
        except ValueError:
            raise ValidationError("invalid milestone values") from None

    @require_auth
    @require_permission("project:create")
    @require_project_access(roles={"manager"})
    async def delete_milestone(self, request, project_id: int, milestone_id: int):
        await self.analytics_svc.delete_milestone(project_id, milestone_id)
        return self.json_ok()

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def cost_details(self, request, project_id: int):
        p = pagination_from(request)
        return self.json(
            await self.analytics_svc.cost_details(
                project_id, request.args.get("ym"), p.page, p.size
            )
        )

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def project_analysis(self, request, project_id: int):
        return self.json(await self.analytics_svc.project_analysis(project_id, request.args.get("ym")))

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def month_comparison(self, request, project_id: int):
        return self.json(
            await self.analytics_svc.month_comparison(
                project_id, (request.json or {}).get("months", [])
            )
        )

    @require_auth
    @require_permission("data:delete")
    @require_project_access(roles={"manager"})
    async def delete_monthly_data(self, request, project_id: int, ym: str):
        await self.analytics_svc.delete_monthly_data(project_id, ym)
        return self.json_ok()

    @require_auth
    @require_permission("data:view")
    async def compare_projects(self, request):
        try:
            body = request.json or {}
            ids = [int(v) for v in body.get("project_ids", [])]
            return self.json(
                await self.analytics_svc.compare_projects(
                    await self._project_scope(request, ids), body.get("ym")
                )
            )
        except (TypeError, ValueError):
            raise ValidationError("invalid project_ids") from None

    # ── report endpoints ────────────────────────────────────────────────

    @require_auth
    @require_permission("data:view")
    async def cost_categories(self, request):
        try:
            raw = request.args.get("project_ids", "")
            ids = [int(v) for v in raw.split(",") if v.strip()]
            ids = await self._project_scope(request, ids or None)
            return self.json(await self.analytics_svc.cost_categories(
                ids, request.args.get("ym"), pagination_from(request, max_size=100),
            ))
        except ValueError:
            raise ValidationError("invalid project_ids") from None

    @require_auth
    @require_permission("data:view")
    async def project_profits(self, request):
        p = pagination_from(request)
        return self.json(
            await self.analytics_svc.project_profits(
                request.args.get("ym"),
                p.page,
                p.size,
                await self._project_scope(request),
            )
        )
    # ── dashboard endpoints ─────────────────────────────────────────────

    @require_auth
    @require_permission("data:view")
    async def dashboard(self, request):
        return self.json(await self.analytics_svc.dashboard(await self._project_scope(request)))

    @require_auth
    @require_permission("data:view")
    async def dashboard_summary(self, request):
        return self.json(
            (await self.analytics_svc.dashboard(await self._project_scope(request)))["summary"]
        )

    @require_auth
    @require_permission("data:view")
    async def dashboard_trends(self, request):
        return self.json(
            {
                "data": await self.analytics_svc.dashboard_trends(
                    await self._project_scope(request)
                )
            }
        )

    @require_auth
    @require_permission("data:view")
    async def dashboard_cost(self, request):
        return self.json(
            {
                "data": await self.analytics_svc.cost_composition(
                    await self._project_scope(request)
                )
            }
        )

    @require_auth
    @require_permission("data:view")
    async def dashboard_health(self, request):
        return self.json(
            await self.analytics_svc.health_radar(await self._project_scope(request))
        )

    @require_auth
    @require_permission("data:view")
    async def dashboard_status(self, request):
        p = pagination_from(request)
        result = await self.analytics_svc.dashboard(await self._project_scope(request))
        rows = result["project_status"]
        start = (p.page - 1) * p.size
        return self.json(
            {
                "projects": rows[start : start + p.size],
                "pagination": {"page": p.page, "size": p.size, "total": len(rows)},
            }
        )

    @require_auth
    @require_permission("data:view")
    async def dashboard_alerts(self, request):
        result = await self.alert_svc.find(
            project_ids=await self._project_scope(request),
            status=request.args.get("status", "active"),
            level=request.args.get("level", ""), pagination=pagination_from(request),
        )
        return self.json(result)
    # ── notification endpoints ──────────────────────────────────────────

    @require_auth
    async def notifications(self, request):
        p = pagination_from(request)
        return self.json(
            await self.analytics_svc.notifications(
                request.ctx.user_id,
                p.page,
                p.size,
                request.args.get("unread_only", "false").lower() == "true",
                await self._project_scope(request),
            )
        )

    @require_auth
    @require_permission("user:manage")
    async def create_notification(self, request):
        return self.json(
            await self.analytics_svc.create_notification(request.json or {}), status=201
        )

    @require_auth
    async def mark_read(self, request, notification_id: int):
        await self.analytics_svc.mark_notification_read(request.ctx.user_id, notification_id)
        return self.json_ok()
    # ── misc ────────────────────────────────────────────────────────────

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def ai_analysis(self, request, project_id: int):
        return self.json(
            await self.analytics_svc.ai_analysis(project_id, (request.json or {}).get("ym"))
        )

    @require_auth
    async def global_search(self, request):
        p = pagination_from(request)
        permissions = set(request.ctx.permissions or set())
        return self.json(
            await self.analytics_svc.global_search(
                request.args.get("keyword", ""),
                p.page,
                p.size,
                await self._project_scope(request),
                "user:manage" in permissions or "admin:roles" in permissions,
            )
        )

    @require_auth
    async def sync_status(self, request):
        return self.json(await self.analytics_svc.sync_status())

    # ── export endpoints ────────────────────────────────────────────────

    @require_auth
    @require_permission("data:export")
    async def export_profits(self, request):
        result = await self.analytics_svc.project_profits(
            request.args.get("ym"), 1, 100, await self._project_scope(request)
        )
        wb = Workbook()
        ws = wb.active
        ws.title = "项目毛利"
        ws.append(["项目编号", "项目名称", "月份", "收入", "成本", "毛利", "毛利率"])
        for item in result["projects"]:
            c = item["current"]
            ws.append([item["project_code"], item["project_name"], item["ym"],
                       c["revenue"], c["cost"], c["profit"], c["profit_rate"]])
        return _xlsx(wb, "project-profits.xlsx")

    @require_auth
    @require_permission("data:export")
    async def export_costs(self, request):
        try:
            ids = [int(v) for v in request.args.get("project_ids", "").split(",") if v]
            ids = await self._project_scope(request, ids or None)
            result = await self.analytics_svc.cost_categories(ids, request.args.get("ym"), 1, 100)
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        wb = Workbook()
        ws = wb.active
        ws.title = "成本科目"
        ws.append(["项目", "月份", "科目", "指标", "实际", "偏差", "偏差率"])
        for proj in result["projects"]:
            for item in proj["items"]:
                ws.append([proj["project"]["name"], proj["ym"], item["name"],
                           item["indicator"], item["actual"], item["deviation"],
                           item["deviation_rate"]])
        return _xlsx(wb, "cost-categories.xlsx")

    @require_auth
    @require_permission("data:export")
    @require_project_access()
    async def export_project(self, request, project_id: int):
        result = await self.analytics_svc.project_analysis(project_id, request.args.get("ym"))
        wb = Workbook()
        overview = wb.active
        overview.title = "项目概览"
        for k, v in result["project"].items():
            overview.append([k, v])
        costs = wb.create_sheet("成本明细")
        costs.append(["科目", "指标", "实际", "偏差", "偏差率"])
        for item in result["cost_categories"]:
            costs.append([item["name"], item["indicator"], item["actual"],
                          item["deviation"], item["deviation_rate"]])
        return _xlsx(wb, f"project-{project_id}.xlsx")

