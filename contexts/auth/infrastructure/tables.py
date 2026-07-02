"""SQLAlchemy Core table definitions + ORM mapped classes for the auth context."""

import sqlalchemy as sa

from contexts.shared.infrastructure.database.metadata import metadata, mapper_registry, _OrmBase

# ── Core tables ──────────────────────────────────────────────────────────────

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

# ── ORM mapped classes ───────────────────────────────────────────────────────

@mapper_registry.mapped
class User(_OrmBase):
    __table__ = users


@mapper_registry.mapped
class Role(_OrmBase):
    __table__ = roles


@mapper_registry.mapped
class Permission(_OrmBase):
    __table__ = permissions


@mapper_registry.mapped
class UserRole(_OrmBase):
    __table__ = user_roles


@mapper_registry.mapped
class RolePermission(_OrmBase):
    __table__ = role_permissions
