from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
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
