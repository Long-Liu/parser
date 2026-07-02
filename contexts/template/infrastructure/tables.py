"""SQLAlchemy Core table definition + ORM mapped class for the template context."""

import sqlalchemy as sa

from contexts.shared.infrastructure.database.metadata import metadata, mapper_registry, _OrmBase

# ── Core table ───────────────────────────────────────────────────────────────

template_configs = sa.Table(
    "template_configs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("template_id", sa.String(100), nullable=False, unique=True),
    sa.Column("description", sa.String(500)),
    sa.Column("config_yaml", sa.Text, nullable=False),
    sa.Column("data_table", sa.String(100), nullable=False),
    sa.Column("is_active", sa.Boolean, default=True),
    sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
)

# ── ORM mapped class ─────────────────────────────────────────────────────────

@mapper_registry.mapped
class TemplateConfig(_OrmBase):
    __table__ = template_configs
