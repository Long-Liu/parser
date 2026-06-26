"""SQLAlchemy Core table definitions — used with aiomysql for type-safe SQL generation."""

import sqlalchemy as sa

metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("username", sa.String(50), nullable=False, unique=True),
    sa.Column("password", sa.String(255), nullable=False),
    sa.Column("real_name", sa.String(100)),
    sa.Column("email", sa.String(200)),
    sa.Column("phone", sa.String(20)),
    sa.Column("is_active", sa.Boolean, default=True),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

roles = sa.Table(
    "roles",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(50), nullable=False, unique=True),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("description", sa.String(500)),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

permissions = sa.Table(
    "permissions",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(100), nullable=False, unique=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.String(500)),
)

user_roles = sa.Table(
    "user_roles",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
    sa.UniqueConstraint("user_id", "role_id"),
)

role_permissions = sa.Table(
    "role_permissions",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
    sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id"), nullable=False),
    sa.UniqueConstraint("role_id", "permission_id"),
)

projects = sa.Table(
    "projects",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(50), nullable=False, unique=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

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
)

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

# --- dynamic data_{template_id} tables ---

_DATA_TYPE_MAP = {
    "int": sa.Integer,
    "bigint": sa.BigInteger,
    "decimal": sa.Numeric,
    "varchar": sa.String,
    "text": sa.Text,
    "json": sa.JSON,
    "datetime": sa.DateTime,
}


def _sa_type(col_type: str):
    """Map a config column type like 'decimal(18,2)' to a SA type."""
    base = col_type.split("(")[0].strip().lower()
    return _DATA_TYPE_MAP.get(base, sa.String)


def data_table_for(template_id: str, columns: list[dict]) -> sa.Table:
    """Build a SA Core Table for a data_{template_id} table from template config.

    Usage:
        dt = data_table_for("social_insurance", cfg["columns"])
        result = await execute(dt.select().where(dt.c.batch_id == 123))
    """
    col_objs = [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer, nullable=False),
        sa.Column("hierarchy_code", sa.String(50)),
    ]
    for col in columns:
        col_objs.append(sa.Column(col["db_field"], _sa_type(col.get("type", "varchar(255)"))))
    col_objs += [
        sa.Column("monthly_data", sa.JSON),
        sa.Column("created_at", sa.DateTime),
    ]
    return sa.Table(f"data_{template_id}", sa.MetaData(), *col_objs)
