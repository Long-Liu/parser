from __future__ import annotations

import asyncio
import io
from typing import Any, cast

from openpyxl import Workbook
from sanic.response import raw

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.analytics.application.analytics_service import AnalyticsApplicationService
from contexts.analytics.infrastructure.xlsx_export import (
    build_budget_lease_writeoff_workbook,
    build_compare_workbook,
    build_cost_categories_workbook,
    build_month_comparison_workbook,
    build_project_export_workbook,
    build_profits_workbook,
    content_disposition,
)
from contexts.auth.application.project_access import (
    ProjectAccessPolicy,
    resolve_project_scope,
)
from contexts.auth.interface.auth_middleware import (
    require_auth,
    require_permission,
    require_project_access,
)
from contexts.auth.interface.request_context import current_auth
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.shared.domain.pagination import Pagination
from contexts.shared.interface.base_controller import BaseController
from contexts.shared.interface.controller_helpers import pagination_from

# 导出全量上限：项目/科目数量级远低于此值，等价于全量导出。
_EXPORT_PAGE = Pagination(1, 10_000, max_size=10_000)


def _project_ids_from_query(raw_ids: str) -> list[int]:
    """Parse a comma-separated project_ids query value ('' -> [])."""
    return [int(v) for v in raw_ids.split(",") if v.strip()]


async def _xlsx(workbook: Workbook, filename: str, fallback: str):
    def serialize() -> bytes:
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

    content = await asyncio.to_thread(serialize)
    return raw(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition(filename, fallback)},
    )


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

    async def _project_scope(self, request, requested: list[int] | None = None) -> list[int] | None:
        auth = current_auth(request)
        return await resolve_project_scope(
            self.access_policy,
            UserId(auth.user_id),
            set(auth.permissions),
            requested,
        )

    def setup(self):
        r = self.bp.add_route
        r(self.summary, "/projects/summary", methods=["GET"])
        r(self.monthly_data, "/projects/<project_id:int>/monthly-data", methods=["GET"])
        r(self.cost_details, "/projects/<project_id:int>/cost-details", methods=["GET"])
        r(self.project_analysis, "/projects/<project_id:int>/analysis", methods=["GET"])
        r(self.month_comparison, "/projects/<project_id:int>/month-comparison", methods=["POST"])
        r(self.delete_monthly_data, "/projects/<project_id:int>/monthly-data/<ym:str>", methods=["DELETE"])
        r(self.compare_projects, "/projects/compare", methods=["POST"])
        r(self.cost_categories, "/reports/cost-categories", methods=["GET"])
        r(self.project_profits, "/reports/project-profits", methods=["GET"])
        r(self.budget_lease_writeoffs, "/reports/budget-lease-writeoffs", methods=["GET"])
        r(self.dashboard, "/dashboard", methods=["GET"])
        r(self.dashboard_summary, "/dashboard/summary", methods=["GET"])
        r(self.dashboard_trends, "/dashboard/trends", methods=["GET"])
        r(self.dashboard_cost, "/dashboard/cost-composition", methods=["GET"])
        r(self.dashboard_health, "/dashboard/health", methods=["GET"])
        r(self.dashboard_status, "/dashboard/project-status", methods=["GET"])
        r(self.dashboard_alerts, "/dashboard/alerts", methods=["GET"])
        r(self.ai_analysis, "/projects/<project_id:int>/ai-analysis", methods=["POST"])
        r(self.global_search, "/search", methods=["GET"])
        r(self.sync_status, "/system/sync-status", methods=["GET"])
        r(self.export_profits, "/reports/project-profits/export", methods=["GET"])
        r(self.export_costs, "/reports/cost-categories/export", methods=["GET"])
        r(self.export_budget_lease_writeoffs, "/reports/budget-lease-writeoffs/export", methods=["GET"])
        r(self.export_project, "/projects/<project_id:int>/export", methods=["GET"])
        r(self.export_month_comparison, "/projects/<project_id:int>/month-comparison/export", methods=["GET"])
        r(self.export_compare, "/projects/compare/export", methods=["GET"])
        r(self.compare_ai_analysis, "/projects/compare/ai-analysis", methods=["POST"])

    # ── project endpoints ──────────────────────────────────────────────

    @require_auth
    @require_permission("project:view")
    async def summary(self, request):
        return self.json(await self.analytics_svc.project_summary(await self._project_scope(request)))

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def monthly_data(self, request, project_id: int):
        return self.json(await self.analytics_svc.monthly_data(project_id, pagination_from(request)))

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def cost_details(self, request, project_id: int):
        p = pagination_from(request)
        return self.json(await self.analytics_svc.cost_details(project_id, request.args.get("ym"), p))

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def project_analysis(self, request, project_id: int):
        return self.json(await self.analytics_svc.project_analysis(project_id, request.args.get("ym")))

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def month_comparison(self, request, project_id: int):
        return self.json(await self.analytics_svc.month_comparison(project_id, (request.json or {}).get("months", [])))

    @require_auth
    @require_permission("data:delete")
    @require_project_access(roles={"manager"})
    async def delete_monthly_data(self, _request, project_id: int, ym: str):
        await self.analytics_svc.delete_monthly_data(project_id, ym)
        return self.json_ok()

    @require_auth
    @require_permission("data:view")
    async def compare_projects(self, request):
        try:
            body = request.json or {}
            ids = [int(v) for v in body.get("project_ids", [])]
            return self.json(
                await self.analytics_svc.compare_projects(await self._project_scope(request, ids), body.get("ym"))
            )
        except (TypeError, ValueError):
            raise ValidationError("invalid project_ids") from None

    # ── report endpoints ────────────────────────────────────────────────

    @require_auth
    @require_permission("data:view")
    async def cost_categories(self, request):
        try:
            ids = _project_ids_from_query(request.args.get("project_ids", ""))
            ids = await self._project_scope(request, ids or None)
            return self.json(
                await self.analytics_svc.cost_categories(
                    ids,
                    request.args.get("ym"),
                    pagination_from(request, max_size=100),
                )
            )
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

    @require_auth
    @require_permission("data:view")
    async def budget_lease_writeoffs(self, request):
        try:
            ids = _project_ids_from_query(request.args.get("project_ids", ""))
            ids = await self._project_scope(request, ids or None)
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        return self.json(
            await self.analytics_svc.budget_lease_writeoffs(
                request.args.get("ym"),
                pagination_from(request, max_size=100),
                ids,
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
        return self.json(await self.analytics_svc.dashboard_summary(await self._project_scope(request)))

    @require_auth
    @require_permission("data:view")
    async def dashboard_trends(self, request):
        return self.json({"data": await self.analytics_svc.dashboard_trends(await self._project_scope(request))})

    @require_auth
    @require_permission("data:view")
    async def dashboard_cost(self, request):
        return self.json({"data": await self.analytics_svc.cost_composition(await self._project_scope(request))})

    @require_auth
    @require_permission("data:view")
    async def dashboard_health(self, request):
        return self.json(await self.analytics_svc.health_radar(await self._project_scope(request)))

    @require_auth
    @require_permission("data:view")
    async def dashboard_status(self, request):
        p = pagination_from(request)
        return self.json(await self.analytics_svc.dashboard_status(await self._project_scope(request), p))

    @require_auth
    @require_permission("data:view")
    async def dashboard_alerts(self, request):
        result = await self.alert_svc.find(
            project_ids=await self._project_scope(request),
            status=request.args.get("status", "active"),
            level=request.args.get("level", ""),
            pagination=pagination_from(request),
        )
        return self.json(result)

    # ── misc ────────────────────────────────────────────────────────────

    @require_auth
    @require_permission("data:view")
    @require_project_access()
    async def ai_analysis(self, request, project_id: int):
        return self.json(await self.analytics_svc.ai_analysis(project_id, (request.json or {}).get("ym")))

    @require_auth
    async def global_search(self, request):
        p = pagination_from(request)
        permissions = set(current_auth(request).permissions)
        return self.json(
            await self.analytics_svc.global_search(
                request.args.get("keyword", ""),
                p,
                await self._project_scope(request),
                ProjectAccessPolicy.has_elevated_permission(permissions),
            )
        )

    @require_auth
    @require_permission("data:view")
    async def sync_status(self, _request):
        return self.json(await self.analytics_svc.sync_status())

    # ── export endpoints ────────────────────────────────────────────────

    @require_auth
    @require_permission("data:export")
    async def export_profits(self, request):
        ym = request.args.get("ym")
        result = await self.analytics_svc.project_profits(ym, _EXPORT_PAGE, await self._project_scope(request))
        wb = await asyncio.to_thread(build_profits_workbook, result["projects"])
        return await _xlsx(wb, f"项目毛利情况_{ym or '全部'}.xlsx", "project-profits.xlsx")

    @require_auth
    @require_permission("data:export")
    async def export_costs(self, request):
        try:
            ids = _project_ids_from_query(request.args.get("project_ids", ""))
            ids = await self._project_scope(request, ids or None)
            ym = request.args.get("ym")
            result = await self.analytics_svc.cost_categories(ids, ym, _EXPORT_PAGE)
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        wb = await asyncio.to_thread(build_cost_categories_workbook, result["projects"])
        return await _xlsx(wb, f"成本科目_{ym or '全部'}.xlsx", "cost-categories.xlsx")

    @require_auth
    @require_permission("data:export")
    async def export_budget_lease_writeoffs(self, request):
        try:
            ids = _project_ids_from_query(request.args.get("project_ids", ""))
            ids = await self._project_scope(request, ids or None)
            ym = request.args.get("ym")
            result = await self.analytics_svc.budget_lease_writeoffs(
                ym,
                _EXPORT_PAGE,
                ids,
            )
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        wb = await asyncio.to_thread(build_budget_lease_writeoff_workbook, result)
        return await _xlsx(
            wb,
            f"预算租借核销表_{ym or '最新'}.xlsx",
            "budget-lease-writeoffs.xlsx",
        )

    @require_auth
    @require_permission("data:export")
    @require_project_access()
    async def export_project(self, request, project_id: int):
        result = await self.analytics_svc.project_analysis(project_id, request.args.get("ym"))
        wb = await asyncio.to_thread(build_project_export_workbook, result)
        return await _xlsx(wb, "项目导出_" + result["project"]["name"] + ".xlsx", f"project-{project_id}.xlsx")

    @require_auth
    @require_permission("data:export")
    @require_project_access()
    async def export_month_comparison(self, request, project_id: int):
        months = [m.strip() for m in request.args.get("months", "").split(",") if m.strip()]
        result = await self.analytics_svc.month_comparison(project_id, months)
        yms = [m["ym"] for m in result["months"]]
        wb = await asyncio.to_thread(build_month_comparison_workbook, cast(Any, result))
        return await _xlsx(wb, "月度对比_" + "_".join(yms) + ".xlsx", f"month-comparison-{project_id}.xlsx")

    @require_auth
    @require_permission("data:export")
    async def export_compare(self, request):
        try:
            ids = _project_ids_from_query(request.args.get("project_ids", ""))
            ids = await self._project_scope(request, ids or None)
            ym = request.args.get("ym")
            result = await self.analytics_svc.compare_projects(ids, ym)
        except ValueError:
            raise ValidationError("invalid project_ids") from None
        wb = await asyncio.to_thread(build_compare_workbook, result)
        return await _xlsx(wb, f"多项目对比_{ym or '最新'}.xlsx", "project-compare.xlsx")

    @require_auth
    @require_permission("data:view")
    async def compare_ai_analysis(self, request):
        try:
            body = request.json or {}
            ids = [int(v) for v in body.get("project_ids", [])]
        except (TypeError, ValueError):
            raise ValidationError("invalid project_ids") from None
        return self.json(
            await self.analytics_svc.compare_ai_analysis(await self._project_scope(request, ids), body.get("ym"))
        )
