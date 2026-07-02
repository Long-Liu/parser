"""SQLAlchemy Core table definitions + ORM mapped classes for the parsing context."""

import sqlalchemy as sa

from contexts.shared.infrastructure.database.metadata import metadata, mapper_registry, _OrmBase

# ── Core tables ──────────────────────────────────────────────────────────────

upload_batches = sa.Table(
    "upload_batches",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_no", sa.String(50), nullable=False, unique=True),
    sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
    sa.Column("ym", sa.String(7), nullable=False),
    sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("file_name", sa.String(500)),
    sa.Column("file_size", sa.BigInteger),
    sa.Column("status", sa.String(20), default="processing"),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

upload_logs = sa.Table(
    "upload_logs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("sheet_name", sa.String(200)),
    sa.Column("template_id", sa.String(100)),
    sa.Column("action", sa.String(20), default="matched"),
    sa.Column("total_rows", sa.Integer, default=0),
    sa.Column("success_rows", sa.Integer, default=0),
    sa.Column("error_rows", sa.Integer, default=0),
    sa.Column("error_msg", sa.Text),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
)

# ── ORM mapped classes ───────────────────────────────────────────────────────

@mapper_registry.mapped
class UploadBatch(_OrmBase):
    __table__ = upload_batches


@mapper_registry.mapped
class UploadLog(_OrmBase):
    __table__ = upload_logs
