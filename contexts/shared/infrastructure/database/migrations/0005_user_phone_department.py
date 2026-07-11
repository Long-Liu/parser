from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    operations = [
        ops.AddField("User", "phone", fields.CharField(max_length=20, null=True)),
        ops.AddField("User", "department", fields.CharField(max_length=100, null=True)),
    ]
