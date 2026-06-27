from sqlalchemy.dialects.mysql import insert as mysql_insert

from db.connection import execute
from db.tables import template_configs
from repositories.base import BaseRepo


class TemplateRepo(BaseRepo):
    table = template_configs

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
        result = await execute(stmt)
        if result.lastrowid:
            return result.lastrowid
        row = await cls.get(template_configs.c.template_id == template_id)
        return row["id"] if row else 0
