"""SQLAlchemy Core table definition + ORM mapped class for the project context."""

import sqlalchemy as sa

from contexts.shared.infrastructure.database.metadata import metadata, mapper_registry, _OrmBase

# ── Core table ───────────────────────────────────────────────────────────────

projects = sa.Table(
    "projects",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(50), nullable=False, unique=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

# ── ORM mapped class ─────────────────────────────────────────────────────────

@mapper_registry.mapped
class Project(_OrmBase):
    __table__ = projects
