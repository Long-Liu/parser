"""Wipe import-domain data, then re-import the 电源A project workbook.

Usage: .venv\\Scripts\\python.exe scripts/reimport_excel.py
"""

import asyncio
from pathlib import Path

from contexts.container import build_container
from contexts.parsing.application.dto import UploadedFile
from contexts.parsing.domain.year_month import YearMonth
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.infrastructure.config import load_settings
from contexts.shared.infrastructure.database.engine import close as db_close
from contexts.shared.infrastructure.database.engine import init as db_init
from contexts.shared.infrastructure.database.schema import migrate_db

EXCEL = Path("excel/01 电源A项目动态成本基础表-0714.xlsx")
PROJECT_ID = 2  # VERIFY-CC（旧 batch 78 同项目）
YM = "2026-07"
USER_ID = 1  # admin

# 导入域数据：批次/日志/预览、15 张解析数据表、由导入派生的告警数据。
# 保留 auth（用户/角色/权限）与项目主数据（导入的前置条件）。
WIPE_TABLES = [
    "upload_batches",
    "upload_logs",
    "upload_previews",
    "data_bid_comparison",
    "data_budget_adjustment_internal",
    "data_budget_adjustment_summary",
    "data_budget_increase",
    "data_budget_lease",
    "data_construction_dynamic",
    "data_dynamic_indicator",
    "data_installation_dynamic",
    "data_labor_cost",
    "data_machinery",
    "data_material_cost",
    "data_other_items",
    "data_settlement_output",
    "data_site_management",
    "data_social_insurance",
    "alerts",
    "alert_events",
    "alert_outbox",
    "alert_rule_states",
]


async def main() -> None:
    settings = load_settings()
    await db_init(settings)
    await migrate_db(settings)

    # noinspection PyPackageRequirements
    from tortoise import connections

    conn = connections.get("default")
    for table in WIPE_TABLES:
        await conn.execute_query(f"DELETE FROM `{table}`")
    print(f"wiped {len(WIPE_TABLES)} tables")

    components = build_container(settings)
    result = await components.upload_service.process(
        UploadedFile(name=EXCEL.name, body=EXCEL.read_bytes()),
        ProjectId(PROJECT_ID),
        YearMonth.parse(YM),
        UserId(USER_ID),
    )
    print("import result:", result)
    # 等告警评估后台任务落定，再关连接
    await components.event_bus.drain()
    await asyncio.sleep(1)
    await db_close()


if __name__ == "__main__":
    asyncio.run(main())
