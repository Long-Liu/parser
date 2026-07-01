"""DDL helpers — generate CREATE TABLE from SA Core definitions."""

from sqlalchemy import schema as sa_schema
from sqlalchemy.dialects.mysql import dialect as mysql_dialect
from sqlalchemy import text

from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.tables import (
    users, roles, permissions, user_roles, role_permissions,
    projects, upload_batches, upload_logs, template_configs,
    TEMPLATE_DATA_TABLES,
)

ALL_TABLES = [users, roles, permissions, user_roles, role_permissions,
              projects, upload_batches, upload_logs, template_configs]

_mysql = mysql_dialect()


async def init_db():
    """Create all fixed application tables if they don't exist."""
    async with get_sessionmaker().begin() as session:
        for table in ALL_TABLES:
            ddl = str(sa_schema.CreateTable(table, if_not_exists=True).compile(dialect=_mysql))
            await session.execute(text(ddl))


async def create_data_table(template_id: str):
    """Create a data_{template_id} table via DDL generated from its SA Table definition."""
    table = TEMPLATE_DATA_TABLES.get(template_id)
    if table is None:
        raise ValueError(f"unknown template: {template_id}")
    ddl = str(sa_schema.CreateTable(table, if_not_exists=True).compile(dialect=_mysql))
    async with get_sessionmaker().begin() as session:
        await session.execute(text(ddl))
