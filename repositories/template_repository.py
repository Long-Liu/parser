from sqlalchemy.dialects.mysql import insert as mysql_insert

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
        """INSERT ... ON DUPLICATE KEY UPDATE. Returns row id."""
        stmt = mysql_insert(cls._t()).values(
            template_id=template_id, description=description,
            config_yaml=config_yaml, data_table=data_table,
        )
        stmt = stmt.on_duplicate_key_update(
            config_yaml=stmt.inserted.config_yaml,
            data_table=stmt.inserted.data_table,
            description=stmt.inserted.description,
        )
        result = await cls._write(stmt)
        if result:
            return result
        row = await cls.get(cls._t().c.template_id == template_id)
        return row["id"] if row else 0
