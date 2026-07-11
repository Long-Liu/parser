"""Add phone and department columns to users table.

These fields exist in the ORM model but the table was created before they
were added to the initial migration (0001 uses initial=True so it skips
already-existing tables).
"""

from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    operations = [
        ops.AddField("User", "phone", fields.CharField(max_length=20, null=True)),
        ops.AddField("User", "department", fields.CharField(max_length=100, null=True)),
    ]
