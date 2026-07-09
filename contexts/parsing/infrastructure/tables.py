"""Tortoise models for the parsing context."""

from tortoise import fields
from tortoise.models import Model


class UploadBatch(Model):
    id = fields.IntField(primary_key=True)
    batch_no = fields.CharField(max_length=50, unique=True)
    project_id = fields.IntField()
    ym = fields.CharField(max_length=7)
    uploaded_by = fields.IntField(null=True)
    file_name = fields.CharField(max_length=500, null=True)
    file_size = fields.BigIntField(null=True)
    status = fields.CharField(max_length=20, default="processing")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "upload_batches"


class UploadLog(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    sheet_name = fields.CharField(max_length=200, null=True)
    template_id = fields.CharField(max_length=100, null=True)
    action = fields.CharField(max_length=20, default="matched")
    total_rows = fields.IntField(default=0)
    success_rows = fields.IntField(default=0)
    error_rows = fields.IntField(default=0)
    error_msg = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "upload_logs"
        indexes = (("batch_id",),)
