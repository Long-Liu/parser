"""Tortoise model for the project context."""

from tortoise import fields
from tortoise.models import Model


class Project(Model):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=200)
    project_type = fields.CharField(max_length=100, null=True)
    capacity_mw = fields.DecimalField(max_digits=12, decimal_places=2, null=True)
    contract_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    start_date = fields.DateField(null=True)
    end_date = fields.DateField(null=True)
    manager_id = fields.IntField(null=True)
    stage = fields.CharField(max_length=50, default="planning")
    status = fields.CharField(max_length=20, default="normal")
    progress = fields.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = fields.TextField(null=True)
    created_by = fields.IntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "projects"


class ProjectUser(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    project_id = fields.IntField()
    is_primary = fields.BooleanField(default=False)
    role = fields.CharField(max_length=20, default="viewer")

    class Meta:
        table = "project_users"
        unique_together = (("user_id", "project_id"),)


class ProjectMilestone(Model):
    id = fields.IntField(primary_key=True)
    project_id = fields.IntField()
    ym = fields.CharField(max_length=7)
    progress = fields.DecimalField(max_digits=5, decimal_places=2, default=0)
    title = fields.CharField(max_length=200)
    description = fields.TextField(null=True)
    completed_at = fields.DateField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "project_milestones"
        indexes = (("project_id", "ym"),)
