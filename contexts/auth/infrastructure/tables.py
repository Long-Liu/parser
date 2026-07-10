"""Tortoise models for the auth context."""

from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=50, unique=True)
    password = fields.CharField(max_length=255)
    real_name = fields.CharField(max_length=100, null=True)
    email = fields.CharField(max_length=200, null=True)
    phone = fields.CharField(max_length=20, null=True)
    department = fields.CharField(max_length=100, null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class Role(Model):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=100)
    description = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "roles"


class Permission(Model):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=100, unique=True)
    name = fields.CharField(max_length=200)
    description = fields.CharField(max_length=500, null=True)

    class Meta:
        table = "permissions"


class UserRole(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    role_id = fields.IntField()

    class Meta:
        table = "user_roles"
        unique_together = (("user_id", "role_id"),)


class RolePermission(Model):
    id = fields.IntField(primary_key=True)
    role_id = fields.IntField()
    permission_id = fields.IntField()

    class Meta:
        table = "role_permissions"
        unique_together = (("role_id", "permission_id"),)
