"""Tortoise model for the project context."""

from tortoise import fields
from tortoise.models import Model


class Project(Model):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=200)
    created_by = fields.IntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "projects"


class ProjectUser(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    project_id = fields.IntField()
    is_primary = fields.BooleanField(default=False)

    class Meta:
        table = "project_users"
        unique_together = (("user_id", "project_id"),)
