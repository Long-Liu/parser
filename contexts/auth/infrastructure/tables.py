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


class Notification(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField(null=True)
    notification_type = fields.CharField(max_length=50, default="system")
    title = fields.CharField(max_length=200)
    message = fields.TextField()
    project_id = fields.IntField(null=True)
    is_read = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notifications"
        indexes = (("user_id", "is_read"),)


class NotificationRead(Model):
    id = fields.IntField(primary_key=True)
    notification_id = fields.IntField()
    user_id = fields.IntField()
    read_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notification_reads"
        unique_together = (("notification_id", "user_id"),)
