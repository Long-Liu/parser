import sqlalchemy as sa

from db.connection import execute
from db.tables import template_configs


async def register_template(template_id: str, description: str,
                            config_yaml: str, data_table: str) -> int:
    result = await execute(sa.text(
        "INSERT INTO template_configs (template_id, description, config_yaml, data_table) "
        "VALUES (:tid, :desc, :yaml, :dt) "
        "ON DUPLICATE KEY UPDATE config_yaml=VALUES(config_yaml), "
        "data_table=VALUES(data_table), description=VALUES(description)"
    ), {"tid": template_id, "desc": description, "yaml": config_yaml, "dt": data_table})
    if result.lastrowid:
        return result.lastrowid
    # ON DUPLICATE KEY UPDATE sets lastrowid=0 — fetch the real id
    row = await get_template_by_id(template_id)
    return row["id"] if row else 0


async def get_template_by_id(template_id: str) -> dict | None:
    result = await execute(template_configs.select().where(
        sa.and_(template_configs.c.template_id == template_id,
                template_configs.c.is_active == True)  # noqa: E712
    ))
    row = await result.fetchone()
    return dict(row) if row else None


async def get_active_templates() -> list[dict]:
    result = await execute(template_configs.select().where(
        template_configs.c.is_active == True  # noqa: E712
    ))
    return [dict(r) for r in await result.fetchall()]
