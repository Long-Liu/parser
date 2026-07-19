from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    # Chained onto 0006 (same pattern as 0006 -> 0005) so Tortoise replays the
    # migrations in filename order 0001..0007 instead of treating this file as
    # an independent graph root.
    dependencies = [('models', '0006_drop_dead_tables')]

    initial = False

    operations = [
        ops.CreateModel(
            name="RevokedToken",
            fields=[
                ("id", fields.IntField(primary_key=True)),
                ("jti", fields.CharField(max_length=64, unique=True)),
                ("user_id", fields.IntField(db_index=True)),
                ("expires_at", fields.DatetimeField(db_index=True)),
                ("revoked_at", fields.DatetimeField(auto_now_add=True)),
            ],
            options={"table": "revoked_tokens", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
