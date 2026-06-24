from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from parser.db.models import TemplateConfig


async def register_template(session: AsyncSession, template_id: str, description: str,
                            config_yaml: str, data_table: str) -> int:
    result = await session.execute(
        select(TemplateConfig).where(TemplateConfig.template_id == template_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.description = description
        existing.config_yaml = config_yaml
        existing.data_table = data_table
    else:
        cfg = TemplateConfig(template_id=template_id, description=description,
                              config_yaml=config_yaml, data_table=data_table)
        session.add(cfg)
    await session.flush()
    return existing.id if existing else cfg.id


async def get_template_by_id(session: AsyncSession, template_id: str) -> TemplateConfig | None:
    result = await session.execute(
        select(TemplateConfig).where(TemplateConfig.template_id == template_id, TemplateConfig.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_active_templates(session: AsyncSession) -> list[TemplateConfig]:
    result = await session.execute(select(TemplateConfig).where(TemplateConfig.is_active == True))
    return result.scalars().all()
