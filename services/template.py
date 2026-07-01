"""Template service — registration + DDL creation."""

from db.schema import create_data_table
from repositories.template import TemplateRepo


async def list_templates() -> list[dict]:
    return await TemplateRepo.list(TemplateRepo._t().c.is_active.is_(True))


async def register_template(template_id: str, config_yaml: str,
                            description: str = "") -> dict:
    data_table = f"data_{template_id}"
    tid = await TemplateRepo.upsert(template_id, description, config_yaml, data_table)
    await create_data_table(template_id)
    return {"id": tid, "table": data_table}
