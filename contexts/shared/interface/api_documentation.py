"""Central OpenAPI documentation for every HTTP controller endpoint.

Keeping the catalogue separate from the application handlers makes the API
contract easy to review and prevents documentation-only code from obscuring
the business workflow in controllers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from inspect import signature
from typing import Any, get_type_hints

from sanic_ext import openapi

JSON = {"application/json": dict}
ERROR = {"application/json": {"error": str}}
OK = {"application/json": {"ok": bool}}
XLSX = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": bytes
}


@dataclass(frozen=True)
class QueryParameter:
    name: str
    schema: type = str
    description: str = ""
    required: bool = False


@dataclass(frozen=True)
class EndpointDoc:
    summary: str
    description: str
    query: tuple[QueryParameter, ...] = ()
    body: Any | None = None
    body_description: str = "JSON 请求体"
    response: Any = field(default_factory=lambda: JSON)
    response_description: str = "请求成功"
    status: int = 200
    secured: bool = True
    paginated: bool = False


PAGE = (
    QueryParameter("page", int, "页码，从 1 开始"),
    QueryParameter("size", int, "每页条数"),
)


def q(name: str, description: str, schema: type = str, required: bool = False):
    return QueryParameter(name, schema, description, required)


def doc(summary: str, description: str, **kwargs) -> EndpointDoc:
    return EndpointDoc(summary, description, **kwargs)


# Request bodies are intentionally explicit: these definitions are the fields
# consumed by controllers, not speculative fields copied from a UI mock-up.
BODIES = {
    "login": {"username": str, "password": str},
    "register": {
        "username": str, "password": str, "real_name": str, "email": str,
        "phone": str, "department": str,
    },
    "change_password": {"old_password": str, "new_password": str},
    "role": {"name": str, "code": str, "description": str, "permissions": [str]},
    "user": {
        "username": str, "password": str, "real_name": str, "email": str,
        "phone": str, "department": str, "status": str,
    },
    "password": {"password": str},
    "permissions": {"permissions": [str]},
    "role_ids": {"role_ids": [int]},
    "project": {
        "code": str, "name": str, "project_type": str, "capacity_mw": float,
        "contract_price": float, "start_date": str, "end_date": str,
        "manager_id": int, "stage": str, "status": str, "progress": float,
        "description": str,
    },
    "project_user": {"is_primary": bool, "role": str},
    "fields": {"fields": dict},
    "alert_rule": dict,
    "note": {"note": str},
    "evaluate": {"ym": str},
    "milestone": dict,
    "months": {"months": [str]},
    "compare": {"project_ids": [int], "ym": str},
    "notification": dict,
    "ai": dict,
}


CATALOG: dict[str, dict[str, EndpointDoc]] = {
    "AuthController": {
        "login": doc("用户登录", "使用用户名和密码换取访问令牌。", body=BODIES["login"], secured=False),
        "register": doc("创建账号", "创建系统账号；关闭开放注册时需要用户管理权限。", body=BODIES["register"], status=201, secured=False),
        "current_user": doc("获取当前用户", "返回当前访问令牌对应的用户信息。"),
        "change_password": doc("修改本人密码", "校验旧密码后修改当前用户密码。", body=BODIES["change_password"]),
        "logout": doc("退出登录", "撤销当前访问令牌。", response=OK),
    },
    "RolesController": {
        "list_roles": doc("角色列表", "查询系统中的全部角色。"),
        "create_role": doc("创建角色", "创建角色并配置权限。", body=BODIES["role"], status=201),
        "get_role": doc("角色详情", "根据角色 ID 查询角色及权限。"),
        "update_role": doc("更新角色", "更新角色基本信息和权限。", body=BODIES["role"]),
        "delete_role": doc("删除角色", "删除指定角色。", response=OK),
        "assign_role": doc("为用户分配角色", "把指定角色分配给指定用户。", response=OK),
        "remove_role": doc("移除用户角色", "移除用户的指定角色。", response=OK),
        "set_user_roles": doc("设置用户角色", "整体替换指定用户的角色列表。", body=BODIES["role_ids"], response=OK),
    },
    "UsersController": {
        "list_users": doc("人员列表", "按关键字查询人员并分页返回。", query=(q("keyword", "姓名、用户名等关键字"),), paginated=True),
        "create_user": doc("创建人员", "创建人员账号。", body=BODIES["user"], status=201),
        "get_user": doc("人员详情", "根据用户 ID 查询人员信息。"),
        "update_user": doc("更新人员", "更新指定人员资料。", body=BODIES["user"]),
        "delete_user": doc("删除人员", "删除指定人员账号。", response=OK),
        "reset_pw": doc("重置人员密码", "管理员为指定人员设置新密码。", body=BODIES["password"], response=OK),
        "get_perms": doc("查询人员权限", "查询指定人员当前拥有的权限。"),
        "set_perms": doc("设置人员权限", "整体替换指定人员的直接权限。", body=BODIES["permissions"], response=OK),
    },
    "ProjectsController": {
        "list_projects": doc("项目列表", "按名称或编码关键字、状态筛选可访问项目。", query=(q("keyword", "项目名称或编码关键字"), q("status", "项目状态")), paginated=True),
        "create_project": doc("创建项目", "创建项目并保存项目基础信息。", body=BODIES["project"], status=201),
        "get_project": doc("项目详情", "查询指定项目的完整信息。"),
        "update_project": doc("更新项目", "更新指定项目的基础信息。", body=BODIES["project"]),
        "delete_project": doc("删除项目", "删除指定项目。", response=OK),
        "assign_user": doc("添加项目成员", "为项目添加成员并设置项目角色。", body=BODIES["project_user"], response=OK),
        "remove_user": doc("移除项目成员", "从项目中移除指定成员。", response=OK),
    },
    "UploadsController": {
        "upload": doc("上传并解析 Excel", "上传 .xlsx 文件并立即执行解析。", body={"multipart/form-data": {"file": bytes, "project_id": int, "ym": str}}, body_description="Excel 文件、项目 ID 和月份", response_description="解析批次结果"),
        "preview": doc("预览 Excel 解析结果", "上传 .xlsx 文件并生成待确认的解析预览。", body={"multipart/form-data": {"file": bytes, "project_id": int, "ym": str}}, body_description="Excel 文件、项目 ID 和月份"),
        "confirm": doc("确认解析预览", "确认预览批次并写入解析数据。"),
        "cancel": doc("取消解析预览", "取消并清理指定预览批次。", response=OK),
    },
    "BatchesController": {
        "list_batches": doc("上传批次列表", "按项目查询当前用户可访问的上传批次。", query=(q("project_id", "项目 ID", int),), paginated=True),
        "get_batch": doc("上传批次详情", "查询批次及各工作表解析结果。"),
    },
    "DataController": {
        "query": doc("解析数据列表", "按模板、批次和动态过滤条件查询解析数据。", query=(q("batch_id", "上传批次 ID", int), q("filter", "过滤条件：字段:操作符:值，可重复")), paginated=True),
        "get_row": doc("解析数据详情", "根据模板和数据行 ID 查询单条解析数据。"),
        "delete": doc("删除解析数据", "删除指定解析数据行。", response=OK),
        "update": doc("更新解析数据", "更新指定数据行的 fields 字段。", body=BODIES["fields"]),
    },
    "TemplatesController": {
        "list_templates": doc("模板列表", "分页查询可用的 Excel 解析模板。", paginated=True),
        "get_template": doc("模板详情", "根据模板标识查询模板定义。"),
        "download_template": doc("下载 Excel 模板", "下载指定模板生成的 Excel 空白文件。", response=XLSX, response_description="Excel 文件"),
    },
    "AlertController": {
        "list_alerts": doc("告警列表", "按状态和级别筛选当前项目范围内的告警。", query=(q("status", "告警状态"), q("level", "告警级别")), paginated=True),
        "summary": doc("告警汇总", "汇总当前用户可访问项目的告警数量。"),
        "rules": doc("告警规则列表", "分页查询告警规则。", paginated=True),
        "update_rule": doc("更新告警规则", "更新指定告警规则配置。", body=BODIES["alert_rule"]),
        "get_alert": doc("告警详情", "查询指定告警详情。"),
        "events": doc("告警事件列表", "分页查询指定告警的状态变化事件。", paginated=True),
        "acknowledge": doc("确认告警", "确认告警并可填写处理备注。", body=BODIES["note"]),
        "resolve": doc("解决告警", "将告警标记为已解决并记录备注。", body=BODIES["note"]),
        "ignore": doc("忽略告警", "将告警标记为已忽略并记录备注。", body=BODIES["note"]),
        "evaluate": doc("执行告警评估", "对指定项目和月份执行告警规则评估。", body=BODIES["evaluate"]),
    },
    "AnalyticsController": {
        "summary": doc("项目统计汇总", "汇总当前用户可访问项目的核心指标。"),
        "monthly_data": doc("项目月度数据", "分页查询指定项目的月度数据。", paginated=True),
        "project_progress": doc("项目进度", "分页查询指定项目的进度记录。", paginated=True),
        "milestones": doc("项目里程碑", "分页查询指定项目的里程碑。", paginated=True),
        "create_milestone": doc("创建里程碑", "为指定项目创建里程碑。", body=BODIES["milestone"], status=201),
        "update_milestone": doc("更新里程碑", "更新指定项目里程碑。", body=BODIES["milestone"]),
        "delete_milestone": doc("删除里程碑", "删除指定项目里程碑。", response=OK),
        "cost_details": doc("项目成本明细", "按月份分页查询项目成本明细。", query=(q("ym", "月份，格式 YYYY-MM"),), paginated=True),
        "project_analysis": doc("项目经营分析", "查询指定项目、月份的经营分析。", query=(q("ym", "月份，格式 YYYY-MM"),)),
        "month_comparison": doc("项目月份对比", "对比指定项目的多个月份数据。", body=BODIES["months"]),
        "delete_monthly_data": doc("删除月度数据", "删除指定项目月份的解析数据。", response=OK),
        "compare_projects": doc("多项目对比", "对比多个项目在指定月份的指标。", body=BODIES["compare"]),
        "cost_categories": doc("成本科目报表", "按项目和月份分页统计成本科目。", query=(q("project_ids", "项目 ID，逗号分隔"), q("ym", "月份，格式 YYYY-MM")), paginated=True),
        "project_profits": doc("项目利润报表", "按月份分页查询项目利润。", query=(q("ym", "月份，格式 YYYY-MM"),), paginated=True),
        "dashboard": doc("驾驶舱数据", "返回驾驶舱所需的完整聚合数据。"),
        "dashboard_summary": doc("驾驶舱汇总", "返回驾驶舱核心汇总指标。"),
        "dashboard_trends": doc("驾驶舱趋势", "返回驾驶舱趋势数据。"),
        "dashboard_cost": doc("驾驶舱成本构成", "返回驾驶舱成本构成数据。"),
        "dashboard_health": doc("驾驶舱项目健康度", "返回项目健康度统计。"),
        "dashboard_status": doc("驾驶舱项目状态", "返回项目状态分布。"),
        "dashboard_alerts": doc("驾驶舱告警", "按状态和级别查询驾驶舱告警。", query=(q("status", "告警状态"), q("level", "告警级别")), paginated=True),
        "notifications": doc("通知列表", "查询当前用户通知。", query=(q("unread_only", "是否仅返回未读通知", bool),), paginated=True),
        "create_notification": doc("创建通知", "管理员创建一条通知。", body=BODIES["notification"], status=201),
        "mark_read": doc("标记通知已读", "将指定通知标记为已读。", response=OK),
        "ai_analysis": doc("项目 AI 分析", "生成指定项目的 AI 分析结果。", body=BODIES["ai"]),
        "global_search": doc("全局搜索", "按关键字搜索项目和业务数据。", query=(q("keyword", "搜索关键字", required=True),)),
        "sync_status": doc("数据同步状态", "查询系统数据同步状态。"),
        "export_profits": doc("导出项目利润", "按月份导出项目利润 Excel。", query=(q("ym", "月份，格式 YYYY-MM"),), response=XLSX, response_description="Excel 文件"),
        "export_costs": doc("导出成本科目", "按项目和月份导出成本科目 Excel。", query=(q("project_ids", "项目 ID，逗号分隔"), q("ym", "月份，格式 YYYY-MM")), response=XLSX, response_description="Excel 文件"),
        "export_project": doc("导出项目数据", "导出指定项目、月份的数据。", query=(q("ym", "月份，格式 YYYY-MM"),), response=XLSX, response_description="Excel 文件"),
        "export_month_comparison": doc("导出月份对比", "导出指定项目的月份对比 Excel。", query=(q("months", "月份，逗号分隔", required=True),), response=XLSX, response_description="Excel 文件"),
        "export_compare": doc("导出项目对比", "导出多项目对比 Excel。", query=(q("project_ids", "项目 ID，逗号分隔", required=True), q("ym", "月份，格式 YYYY-MM")), response=XLSX, response_description="Excel 文件"),
        "compare_ai_analysis": doc("多项目 AI 分析", "生成多项目对比的 AI 分析结果。", body=BODIES["compare"]),
        "mark_all_read": doc("全部通知已读", "将当前用户的全部通知标记为已读。", response=OK),
        "delete_notification": doc("删除通知", "删除当前用户的指定通知。", response=OK),
        "clear_notifications": doc("清空通知", "清空当前用户的全部通知。", response=OK),
    },
}


TAGS = {
    "AuthController": "认证",
    "RolesController": "角色权限",
    "UsersController": "人员管理",
    "ProjectsController": "项目管理",
    "UploadsController": "Excel 上传",
    "BatchesController": "上传批次",
    "DataController": "解析数据",
    "TemplatesController": "解析模板",
    "AlertController": "告警管理",
    "AnalyticsController": "统计分析",
}


def apply_controller_docs(controller) -> None:
    """Attach the catalogue to bound handlers before routes are registered."""
    class_name = type(controller).__name__
    endpoints = CATALOG.get(class_name)
    if endpoints is None:
        raise RuntimeError(f"missing OpenAPI catalogue for {class_name}")

    for method_name, endpoint in endpoints.items():
        handler = getattr(controller, method_name)
        type_hints = get_type_hints(handler)
        handler = openapi.tag(TAGS[class_name])(handler)
        handler = openapi.summary(endpoint.summary)(handler)
        handler = openapi.description(endpoint.description)(handler)

        for name, parameter in signature(handler).parameters.items():
            if name in {"request", "ws"}:
                continue
            annotation = type_hints.get(name, parameter.annotation)
            schema = annotation if annotation in {str, int, float, bool} else str
            handler = openapi.parameter(
                name, schema, "path", description=f"{name} 路径参数", required=True
            )(handler)

        parameters = endpoint.query + (PAGE if endpoint.paginated else ())
        for parameter in parameters:
            handler = openapi.parameter(
                parameter.name,
                parameter.schema,
                "query",
                description=parameter.description,
                required=parameter.required,
            )(handler)

        if endpoint.body is not None:
            body_content = endpoint.body
            if not (
                isinstance(body_content, dict)
                and any("/" in key for key in body_content)
            ):
                body_content = {"application/json": body_content}
            handler = openapi.body(
                body_content,
                required=True,
                description=endpoint.body_description,
            )(handler)

        handler = openapi.response(
            endpoint.status,
            endpoint.response,
            endpoint.response_description,
        )(handler)
        if endpoint.secured:
            handler = openapi.secured("bearerAuth")(handler)
            for status, description in (
                (400, "请求参数错误"),
                (401, "未登录或访问令牌无效"),
                (403, "没有接口或项目访问权限"),
                (404, "资源不存在"),
                (409, "资源状态冲突"),
            ):
                handler = openapi.response(status, ERROR, description)(handler)

        # openapi.body returns a wrapper, so the documented callable must be the
        # one later handed to Blueprint.add_route.
        setattr(controller, method_name, handler)


def documented_endpoint_names(class_name: str) -> set[str]:
    """Expose catalogue coverage for the route contract test."""
    return set(CATALOG.get(class_name, {}))
