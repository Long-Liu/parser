from tortoise import fields, migrations
from tortoise.indexes import Index
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    operations = [
        ops.CreateModel(
            name="UploadPreview",
            fields=[
                ("id", fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ("batch_id", fields.IntField(unique=True)),
                ("payload", fields.JSONField()),
                ("summary", fields.JSONField()),
                ("status", fields.CharField(max_length=20, default="pending")),
                ("created_at", fields.DatetimeField(auto_now_add=True)),
            ],
            options={"table": "upload_previews", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="ProjectMilestone",
            fields=[
                ("id", fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ("project_id", fields.IntField()),
                ("ym", fields.CharField(max_length=7)),
                ("progress", fields.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("title", fields.CharField(max_length=200)),
                ("description", fields.TextField(null=True)),
                ("completed_at", fields.DateField(null=True)),
                ("created_at", fields.DatetimeField(auto_now_add=True)),
            ],
            options={"table": "project_milestones", "app": "models",
                     "indexes": [Index(fields=["project_id", "ym"])], "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Notification",
            fields=[
                ("id", fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ("user_id", fields.IntField(null=True)),
                ("notification_type", fields.CharField(max_length=50, default="system")),
                ("title", fields.CharField(max_length=200)),
                ("message", fields.TextField()),
                ("project_id", fields.IntField(null=True)),
                ("is_read", fields.BooleanField(default=False)),
                ("created_at", fields.DatetimeField(auto_now_add=True)),
            ],
            options={"table": "notifications", "app": "models",
                     "indexes": [Index(fields=["user_id", "is_read"])], "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.AddField("Project", "project_type", fields.CharField(max_length=100, null=True)),
        ops.AddField("Project", "capacity_mw", fields.DecimalField(max_digits=12, decimal_places=2, null=True)),
        ops.AddField("Project", "contract_price", fields.DecimalField(max_digits=15, decimal_places=2, null=True)),
        ops.AddField("Project", "start_date", fields.DateField(null=True)),
        ops.AddField("Project", "end_date", fields.DateField(null=True)),
        ops.AddField("Project", "manager_id", fields.IntField(null=True)),
        ops.AddField("Project", "stage", fields.CharField(max_length=50, default="planning")),
        ops.AddField("Project", "status", fields.CharField(max_length=20, default="normal")),
        ops.AddField("Project", "progress", fields.DecimalField(max_digits=5, decimal_places=2, default=0)),
        ops.AddField("Project", "description", fields.TextField(null=True)),
        ops.AddField("Project", "updated_at", fields.DatetimeField(auto_now=True, null=True)),
        ops.AddField("ProjectUser", "role", fields.CharField(max_length=20, default="viewer")),
        *[
            ops.AddField("DataGrossProfit", name,
                         fields.DecimalField(max_digits=15, decimal_places=decimals, null=True))
            for name, decimals in [
                ("bid_revenue", 2), ("bid_cost", 2), ("bid_profit", 2),
                ("bid_profit_rate", 10), ("indicator_revenue", 2),
                ("indicator_cost", 2), ("indicator_profit", 2),
                ("indicator_profit_rate", 10), ("actual_revenue", 2),
                ("actual_cost", 2), ("actual_profit", 2),
                ("actual_profit_rate", 10), ("forecast_revenue", 2),
                ("forecast_cost", 2), ("forecast_profit", 2),
                ("forecast_profit_rate", 10),
            ]
        ],
    ]
