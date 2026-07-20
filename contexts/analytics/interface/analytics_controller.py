from __future__ import annotations

import io

from openpyxl import Workbook
from sanic.response import raw

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.analytics.application.analytics_service import AnalyticsApplicationService
from contexts.analytics.infrastructure.xlsx_export import (
    build_compare_workbook,
    build_cost_categories_workbook,
    build_month_comparison_workbook,
    build_profits_workbook,
    content_disposition,
)
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.auth.interface.auth_middleware import (
    require_auth,
    require_permission,
    require_project_access,
)
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.shared.domain.pagination import Pagination
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from

# 导出全量上限：项目/科目数量级远低于此值，等价于全量导出。
_EXPORT_PAGE = Pagination(1, 10_000, max_size=10_000)


def _xlsx(workbook: Workbook, filename: str, fallback: str):
    output = io.BytesIO()
    workbook.save(output)
    return raw(output.getvalue(), content_type=(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ), headers={"Content-Disposition": content_disposition(filename, fallback)})

class AnalyticsController(BaseController):
    name = "analytics"

    def __init__(
        self,
        analytics_svc: AnalyticsApplicationService,
        access_policy: ProjectAccessPolicy,
        alert_svc: AlertApplicationService,
    ):
        super().__init__()
        self.analytics_svc = analytics_svc
        self.access_policy = access_policy
        self.alert_svc = alert_svc

    async def _project_scope(
        self, request, requested: list[int] | None = None
    ) -> list[int] | None:
        permissions = set(request.ctx.permissions or set())
        if ProjectAccessPolicy.has_elevated_permission(permissions):
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
        r(self.export_month_comparison,
          "/projects/<project_id:int>/month-comparison/export",         methods=["GET"])
        r(self.export_compare,      "/projects/compare/export",             methods=["GET"])
        r(self.compare_ai_analysis, "/projects/compare/ai-analysis",        methods=["POST"])
        r(self.mark_all_read,       "/notifications/read-all",              methods=["POST"])
        r(self.delete_notification, "/notifications/<notification_id:int>", methods=["DELETE"])
        r(self.clear_notifications, "/notifications",                       methods=["DELETE"])

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
                project_id, request.args.get("ym"), p
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
                p,
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
                p,
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
                p,
                await self._project_scope(request),
                ProjectAccessPolicy.has_elevated_permission(permissions),
            )
        )

    @require_auth
    async def sync_status(self, request):
        return self.json(await self.analytics_svc.sync_status())

    # ── export endpoints ────────────────────────────────────────────────

    @require_auth
    @require_permission("data:export")
    async def export_profits(self, request):
        ym = request.args.get("ym")
        result = await self.analytics_svc.project_profits(
            ym, _EXPORT_PAGE, await self._project_scope(request)
        )
        wb = build_profits_workbook(result["projects"])
        return _xlsx(wb, f"项目毛利情况_{ym or '全部'}.xlsx", "project-profits.xlsx")

    @require_auth
    @require_permission("data:export")
    async def export_costs(self, request):
        try:
            ids = [int(v) for v in request.args.get("project_ids", "").split(",") if v.strip()]
            ids = await self._project_scope(request, ids or None)
            ym = request.args.get("ym")
            result = await self.analytics_svc.cost_categories(ids, ym, _EXPORT_PAGE)
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        wb = build_cost_categories_workbook(result["projects"])
        return _xlsx(wb, f"成本科目_{ym or '全部'}.xlsx", "cost-categories.xlsx")

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
        return _xlsx(wb, "项目导出_" + result["project"]["name"] + ".xlsx",
                     f"project-{project_id}.xlsx")


    @require_auth
    @require_permission("data:export")
    @require_project_access()
    async def export_month_comparison(self, request, project_id: int):
        months = [m.strip() for m in
                  request.args.get("months", "").split(",") if m.strip()]
        result = await self.analytics_svc.month_comparison(project_id, months)
        yms = [m["ym"] for m in result["months"]]
        wb = build_month_comparison_workbook(result)
        return _xlsx(wb, "月度对比_" + "_".join(yms) + ".xlsx",
                     f"month-comparison-{project_id}.xlsx")

    @require_auth
    @require_permission("data:export")
    async def export_compare(self, request):
        try:
            ids = [int(v) for v in request.args.get("project_ids", "").split(",")
                   if v.strip()]
            ids = await self._project_scope(request, ids or None)
            ym = request.args.get("ym")
            result = await self.analytics_svc.compare_projects(ids, ym)
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        wb = build_compare_workbook(result)
        return _xlsx(wb, f"多项目对比_{ym or '最新'}.xlsx", "project-compare.xlsx")

    @require_auth
    @require_permission("data:view")
    async def compare_ai_analysis(self, request):
        try:
            body = request.json or {}
            ids = [int(v) for v in body.get("project_ids", [])]
        except (TypeError, ValueError):
            raise ValidationError("invalid project_ids") from None
        return self.json(
            await self.analytics_svc.compare_ai_analysis(
                await self._project_scope(request, ids), body.get("ym")
            )
        )

    @require_auth
    async def mark_all_read(self, request):
        marked = await self.analytics_svc.mark_all_notifications_read(
            request.ctx.user_id
        )
        return self.json({"ok": True, "marked": marked})

    @require_auth
    async def delete_notification(self, request, notification_id: int):
        await self.analytics_svc.delete_notification(
            request.ctx.user_id, notification_id
        )
        return self.json_ok()

    @require_auth
    async def clear_notifications(self, request):
        deleted = await self.analytics_svc.clear_notifications(request.ctx.user_id)
        return self.json({"ok": True, "deleted": deleted})
