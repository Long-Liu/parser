"""Tortoise model for template configuration rows."""

from tortoise import fields
from tortoise.models import Model


class TemplateConfig(Model):
    id = fields.IntField(primary_key=True)
    template_id = fields.CharField(max_length=100, unique=True)
    description = fields.CharField(max_length=500, null=True)
    config_yaml = fields.TextField()
    data_table = fields.CharField(max_length=100)
    is_active = fields.BooleanField(default=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "template_configs"
