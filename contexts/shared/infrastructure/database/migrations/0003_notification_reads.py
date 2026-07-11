from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    operations = [
        ops.CreateModel(
            name="NotificationRead",
            fields=[
                ("id", fields.IntField(generated=True, primary_key=True,
                                       unique=True, db_index=True)),
                ("notification_id", fields.IntField()),
                ("user_id", fields.IntField()),
                ("read_at", fields.DatetimeField(auto_now_add=True)),
            ],
            options={
                "table": "notification_reads", "app": "models",
                "unique_together": (("notification_id", "user_id"),),
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
    ]
