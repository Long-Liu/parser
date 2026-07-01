import sqlalchemy as sa

from db.models import TemplateConfig
from repositories.base_repository import BaseRepo


class TemplateRepo(BaseRepo):
    model = TemplateConfig

    @classmethod
    async def list_active(cls) -> list[dict]:
        return await cls.list(cls._t().c.is_active.is_(True))

    @classmethod
    async def upsert(cls, template_id: str, description: str,
                     config_yaml: str, data_table: str) -> int:
        """Create or update a template config. Returns row id."""
        row = await cls.get(cls._t().c.template_id == template_id)
        if row:
            await cls.update(
                cls._t().c.id == row["id"],
                config_yaml=config_yaml,
                data_table=data_table,
                description=description,
            )
            return row["id"]

        stmt = sa.insert(cls._t()).values(
            template_id=template_id,
            description=description,
            config_yaml=config_yaml,
            data_table=data_table,
        )
        result = await cls._write(stmt)
        return result.lastrowid or 0
