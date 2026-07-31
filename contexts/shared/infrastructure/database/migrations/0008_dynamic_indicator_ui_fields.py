# ruff: noqa: I001
# noinspection PyPackageRequirements
from tortoise import fields, migrations

# noinspection PyPackageRequirements
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0007_revoked_tokens")]
    initial = False
    operations = [
        ops.AddField("DataDynamicIndicator", "display_level", fields.CharField(max_length=50, null=True)),
        ops.AddField("DataDynamicIndicator", "linked_sheet", fields.CharField(max_length=100, null=True)),
        ops.AddField(
            "DataDynamicIndicator", "adjusted_tax_rate", fields.DecimalField(max_digits=5, decimal_places=4, null=True)
        ),
        ops.AddField(
            "DataDynamicIndicator", "adjusted_tax", fields.DecimalField(max_digits=15, decimal_places=2, null=True)
        ),
        ops.AddField("DataDynamicIndicator", "adjustment", fields.CharField(max_length=100, null=True)),
        ops.AddField(
            "DataDynamicIndicator", "forecast_ex_tax", fields.DecimalField(max_digits=15, decimal_places=2, null=True)
        ),
        ops.AddField(
            "DataDynamicIndicator", "forecast_tax_rate", fields.DecimalField(max_digits=5, decimal_places=4, null=True)
        ),
        ops.AddField(
            "DataDynamicIndicator", "forecast_tax", fields.DecimalField(max_digits=15, decimal_places=2, null=True)
        ),
        ops.AddField(
            "DataDynamicIndicator", "forecast_with_tax", fields.DecimalField(max_digits=15, decimal_places=2, null=True)
        ),
        ops.AddField("DataDynamicIndicator", "forecast_remark", fields.TextField(null=True)),
    ]
